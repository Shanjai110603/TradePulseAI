import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.pattern import Pattern
from app.models.signal import Signal, SignalEvent, SignalTechnicalSnapshot, SignalAIAnalysis, SignalResult
from app.models.telegram import TelegramAccount
from app.models.user import User
from app.engine.market_data.manager import market_data_manager
from app.engine.signals.evaluator import SignalEvaluationPipeline
from app.engine.signals.tracker import SignalLifecycleTracker
from app.engine.ai.mock_ai import MockAIProvider
from app.telegram.bot import telegram_service

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """
    Continuous background worker:
    1. Evaluates active user patterns against fresh candle data
    2. Generates validated signals and enriches with AI
    3. Dispatches notifications to linked Telegram chats
    4. Updates active signal lifecycles and records outcomes
    """

    def __init__(self):
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Background pattern evaluation and signal lifecycle worker started.")

    def stop(self):
        self._is_running = False
        if self._task:
            self._task.cancel()
            logger.info("Background worker stopped.")

    async def _run_loop(self):
        while self._is_running:
            try:
                await self.tick_pattern_evaluation()
                await self.tick_signal_lifecycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background worker tick: {e}", exc_info=True)

            await asyncio.sleep(10)  # Evaluation interval

    async def tick_pattern_evaluation(self):
        """Scans active user patterns against live/mock market data"""
        async with AsyncSessionLocal() as db:
            query = select(Pattern).options(
                selectinload(Pattern.user).selectinload(User.preferences)
            ).where(Pattern.is_active == True)
            res = await db.execute(query)
            active_patterns = res.scalars().all()

            if not active_patterns:
                return

            provider = market_data_manager.get_provider()

            for pattern in active_patterns:
                assets = pattern.assets_config or ["EUR/USD"]
                tf = pattern.timeframe or "1M"

                for asset_symbol in assets:
                    try:
                        candles = await provider.get_candles(asset_symbol, timeframe=tf, limit=50)
                        if len(candles) < 10:
                            continue

                        # Check if a signal was already generated on this latest candle to avoid duplicate signals
                        last_candle = candles[-1]
                        last_ts = datetime.fromtimestamp(last_candle.timestamp, tz=timezone.utc)

                        dup_check = select(Signal.id).where(
                            Signal.pattern_id == pattern.id,
                            Signal.asset_symbol == asset_symbol,
                            Signal.matched_candle_timestamp == last_ts
                        )
                        dup_res = await db.execute(dup_check)
                        if dup_res.scalar_one_or_none():
                            continue

                        pattern_dict = {
                            "id": pattern.id,
                            "name": pattern.name,
                            "market_id": pattern.market_id,
                            "direction": pattern.direction,
                            "timeframe": tf,
                            "asset_symbol": asset_symbol,
                            "current_version": pattern.current_version,
                            "trend_config": pattern.trend_config,
                            "momentum_config": pattern.momentum_config,
                            "volume_config": pattern.volume_config,
                            "indicators_config": pattern.indicators_config,
                            "rules_config": pattern.rules_config,
                            "entry_config": pattern.entry_config,
                            "target_config": pattern.target_config,
                            "ai_config": pattern.ai_config,
                        }

                        user_prefs = None
                        if pattern.user and pattern.user.preferences:
                            prefs = pattern.user.preferences
                            user_prefs = {
                                "min_ai_score": prefs.min_ai_score,
                                "min_confidence": prefs.min_confidence,
                                "risk_per_trade_percent": getattr(prefs, "risk_per_trade_percent", 2.0)
                            }

                        is_created, sig_payload, reason, _ = await SignalEvaluationPipeline.evaluate_candidate(
                            pattern_dict=pattern_dict,
                            candles=candles,
                            user_preferences=user_prefs
                        )

                        if is_created and sig_payload:
                            # Persist Signal to DB
                            new_signal = Signal(
                                id=sig_payload["id"],
                                user_id=pattern.user_id,
                                pattern_id=pattern.id,
                                pattern_version=pattern.current_version,
                                pattern_name=pattern.name,
                                market_id=pattern.market_id,
                                asset_symbol=asset_symbol,
                                direction=sig_payload["direction"],
                                timeframe=tf,
                                reference_price=sig_payload["reference_price"],
                                entry_time=sig_payload["entry_time"],
                                expiry_time=sig_payload["expiry_time"],
                                duration_minutes=sig_payload["duration_minutes"],
                                stop_loss=sig_payload.get("stop_loss"),
                                tp1=sig_payload.get("tp1"),
                                tp2=sig_payload.get("tp2"),
                                tp3=sig_payload.get("tp3"),
                                risk_reward_ratio=sig_payload.get("risk_reward_ratio"),
                                signal_strength=sig_payload["signal_strength"],
                                ai_score=sig_payload["ai_score"],
                                ai_confidence=sig_payload["ai_confidence"],
                                status="ACTIVE",
                                matched_candle_timestamp=last_ts,
                                raw_trigger_candles=sig_payload["raw_trigger_candles"]
                            )
                            db.add(new_signal)

                            # Persist Technical Snapshot
                            tech_snap = SignalTechnicalSnapshot(
                                signal_id=new_signal.id,
                                **{k: v for k, v in sig_payload["technical_snapshot"].items() if hasattr(SignalTechnicalSnapshot, k)}
                            )
                            db.add(tech_snap)

                            # Persist AI Analysis
                            ai_data = sig_payload["ai_analysis"]
                            ai_analysis = SignalAIAnalysis(
                                signal_id=new_signal.id,
                                ai_provider=ai_data.get("raw_response", {}).get("engine", "openrouter_ai"),
                                bias=ai_data.get("bias", "BEARISH"),
                                score=ai_data.get("score", 85),
                                confidence=ai_data.get("confidence", "HIGH"),
                                trend_assessment=ai_data.get("trend_assessment", ""),
                                momentum_assessment=ai_data.get("momentum_assessment", ""),
                                volume_assessment=ai_data.get("volume_assessment", ""),
                                structure_assessment=ai_data.get("structure_assessment", ""),
                                entry_quality=ai_data.get("entry_quality", ""),
                                risk_assessment=ai_data.get("risk_assessment", ""),
                                volatility=ai_data.get("volatility", "Moderate"),
                                key_levels=ai_data.get("key_levels", {}),
                                reasoning=ai_data.get("reasoning", ""),
                                risks=ai_data.get("risks", []),
                                invalidating_conditions=ai_data.get("invalidating_conditions", []),
                                raw_response=ai_data.get("raw_response", {})
                            )
                            db.add(ai_analysis)

                            # Add Signal Event
                            event = SignalEvent(
                                signal_id=new_signal.id,
                                event_type="GENERATED",
                                price=sig_payload["reference_price"],
                                message="Signal generated by deterministic pattern engine",
                                data={"ai_score": sig_payload["ai_score"]}
                            )
                            db.add(event)

                            await db.commit()

                            # Broadcast signal notification to ALL active Telegram subscribers
                            tg_query = select(TelegramAccount).where(
                                TelegramAccount.is_active == True,
                                (TelegramAccount.is_muted == False) | (TelegramAccount.is_muted == None)
                            )
                            tg_res = await db.execute(tg_query)
                            subscribers = tg_res.scalars().all()

                            p_name = pattern.name
                            if "image_path" not in sig_payload or not sig_payload["image_path"]:
                                if "15" in p_name:
                                    sig_payload["image_path"] = "/uploads/patterns/pattern_type_15.jpg"
                                elif "14" in p_name:
                                    sig_payload["image_path"] = "/uploads/patterns/pattern_type_14.jpg"
                                elif "1" in p_name or "SMC" in p_name:
                                    sig_payload["image_path"] = "/uploads/patterns/pattern_type_1.jpg"

                            for sub in subscribers:
                                try:
                                    chat_id = int(sub.telegram_chat_id)
                                    await telegram_service.send_signal_notification(chat_id, sig_payload)
                                except Exception as err:
                                    logger.error(f"Failed to send signal to chat_id {sub.telegram_chat_id}: {err}")

                            logger.info(f"Broadcast signal {new_signal.id} for '{pattern.name}' on {asset_symbol} to {len(subscribers)} Telegram subscriber(s).")

                    except Exception as e:
                        logger.error(f"Error evaluating asset {asset_symbol} for pattern {pattern.name}: {e}")

    async def tick_signal_lifecycle(self):
        """Updates active signals against latest prices and handles expirations"""
        async with AsyncSessionLocal() as db:
            query = select(Signal).where(Signal.status.in_(["ACTIVE", "PENDING", "UPDATE"]))
            res = await db.execute(query)
            active_signals = res.scalars().all()

            if not active_signals:
                return

            provider = market_data_manager.get_provider()

            for signal in active_signals:
                try:
                    current_price = await provider.get_current_price(signal.asset_symbol)
                    sig_dict = {
                        "id": signal.id,
                        "direction": signal.direction,
                        "reference_price": signal.reference_price,
                        "market_id": signal.market_id,
                        "expiry_time": signal.expiry_time,
                        "status": signal.status,
                        "tp1": signal.tp1,
                        "tp2": signal.tp2,
                        "tp3": signal.tp3,
                        "stop_loss": signal.stop_loss
                    }

                    new_status, is_completed, event_info = SignalLifecycleTracker.evaluate_signal_tick(
                        signal_data=sig_dict,
                        current_price=current_price
                    )

                    if new_status != signal.status:
                        signal.status = new_status
                        db.add(SignalEvent(
                            signal_id=signal.id,
                            event_type="STATUS_CHANGE",
                            price=current_price,
                            message=event_info.get("reason", "Status updated"),
                            data=event_info
                        ))

                    if is_completed:
                        # Check if result already recorded
                        res_check = await db.execute(select(SignalResult).where(SignalResult.signal_id == signal.id))
                        if not res_check.scalar_one_or_none():
                            outcome = event_info.get("outcome", "WIN")
                            pnl_pct = event_info.get("pnl_percentage", 0.0)

                            # Post-signal AI debrief
                            ai_mock = MockAIProvider()
                            debrief = await ai_mock.post_signal_analysis(
                                signal_data={"pattern_name": signal.pattern_name, "direction": signal.direction},
                                outcome_data={"outcome": outcome, "exit_price": current_price},
                                historical_candles=[]
                            )

                            result_record = SignalResult(
                                signal_id=signal.id,
                                outcome=outcome,
                                exit_price=current_price,
                                exit_time=datetime.now(timezone.utc),
                                pnl_percentage=pnl_pct,
                                post_analysis_notes=f"AI Alignment: {debrief.ai_alignment_score}%. Notes: {debrief.improvement_notes}"
                            )
                            db.add(result_record)

                    await db.commit()

                except Exception as e:
                    logger.error(f"Error tracking signal {signal.id}: {e}")


background_scheduler = BackgroundScheduler()
