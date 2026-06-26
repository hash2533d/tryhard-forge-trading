import json
from datetime import datetime


class MESSafeAdjustSimulator:
    def __init__(self, initial_entry_price: float, side: str = "long"):
        self.entry_price = initial_entry_price
        self.side = side.lower()
        self.tick_value = 1.25  # MES $1.25 per tick ($5.00 per point)

        # State Flags & Positions
        self.is_active = True
        self.max_favorable_ticks = 0
        self.exit_price = None
        self.exit_reason = None

        # ATM Parameters (Hardcoded from atm_execution_rules.json definition)
        self.initial_stop_ticks = 40
        self.initial_target_ticks = 100

        # Set dynamic thresholds based on entry side
        if self.side == "long":
            self.current_stop = self.entry_price - (self.initial_stop_ticks * 0.25)
            self.current_target = self.entry_price + (self.initial_target_ticks * 0.25)
        else:
            self.current_stop = self.entry_price + (self.initial_stop_ticks * 0.25)
            self.current_target = self.entry_price - (self.initial_target_ticks * 0.25)

        # Strategy Status States
        self.breakeven_triggered = False
        self.trail_step_1_triggered = False
        self.trail_step_2_triggered = False

    def process_tick(self, tick_price: float, timestamp: str):
        if not self.is_active:
            return

        # Calculate current favorable movement distance in ticks
        if self.side == "long":
            favorable_ticks = int((tick_price - self.entry_price) / 0.25)
        else:
            favorable_ticks = int((self.entry_price - tick_price) / 0.25)

        if favorable_ticks > self.max_favorable_ticks:
            self.max_favorable_ticks = favorable_ticks

        # ---------------------------------------------------------------------
        # Dynamic State Rules (ATM Tracking & Discreet Manual Tightening)
        # ---------------------------------------------------------------------

        # 1. Discreet Manual Adjustment: At +10 ticks profit, lower stop to +2 ticks
        if favorable_ticks >= 10 and not self.breakeven_triggered and not self.trail_step_1_triggered:
            new_stop = (
                self.entry_price + (2 * 0.25)
                if self.side == "long"
                else self.entry_price - (2 * 0.25)
            )
            # Ensure we only tighten, never widen
            if (self.side == "long" and new_stop > self.current_stop) or (
                self.side == "short" and new_stop < self.current_stop
            ):
                self.current_stop = new_stop
                print(
                    f"[{timestamp}] [MANUAL TIGHTEN] Profit hit +10 ticks. "
                    f"Stop manually compressed to +2 ticks ({self.current_stop:.2f})."
                )

        # 2. Discreet Manual Adjustment: At +16 ticks profit, pull target back to +20 ticks
        if favorable_ticks >= 16 and self.current_target == (
            self.entry_price + (100 * 0.25)
            if self.side == "long"
            else self.entry_price - (100 * 0.25)
        ):
            self.current_target = (
                self.entry_price + (20 * 0.25)
                if self.side == "long"
                else self.entry_price - (20 * 0.25)
            )
            print(
                f"[{timestamp}] [MANUAL TARGET] Profit hit +16 ticks. "
                f"Target compressed to +20 ticks ({self.current_target:.2f}) to lock gains."
            )

        # 3. Auto-Breakeven Rule: Trigger at +20 ticks, move stop to +5 ticks
        if favorable_ticks >= 20 and not self.breakeven_triggered:
            self.current_stop = (
                self.entry_price + (5 * 0.25)
                if self.side == "long"
                else self.entry_price - (5 * 0.25)
            )
            self.breakeven_triggered = True
            print(
                f"[{timestamp}] [AUTO BREAKEVEN] Profit hit +20 ticks. "
                f"Stop updated to +5 ticks ({self.current_stop:.2f})."
            )

        # 4. Auto-Trail Step 1: Trigger at +25 ticks, trail with a 15-tick offset, frequency 2
        if favorable_ticks >= 25:
            # Calculate trail baseline with frequency step normalization
            normalized_fav = (favorable_ticks // 2) * 2
            calculated_trail_stop = (
                self.entry_price + ((normalized_fav - 15) * 0.25)
                if self.side == "long"
                else self.entry_price - ((normalized_fav - 15) * 0.25)
            )

            if (self.side == "long" and calculated_trail_stop > self.current_stop) or (
                self.side == "short" and calculated_trail_stop < self.current_stop
            ):
                self.current_stop = calculated_trail_stop
                if not self.trail_step_1_triggered:
                    print(f"[{timestamp}] [TRAIL STEP 1] Step activated at +25 ticks.")
                    self.trail_step_1_triggered = True
                print(
                    f"[{timestamp}] [TRAIL UPDATE] Stop trailed to {self.current_stop:.2f} "
                    f"(Locked +{normalized_fav - 15} ticks)."
                )

        # 5. Auto-Trail Step 2: Trigger at +50 ticks, trail with a 10-tick offset, frequency 2
        if favorable_ticks >= 50:
            normalized_fav = (favorable_ticks // 2) * 2
            calculated_trail_stop = (
                self.entry_price + ((normalized_fav - 10) * 0.25)
                if self.side == "long"
                else self.entry_price - ((normalized_fav - 10) * 0.25)
            )

            if (self.side == "long" and calculated_trail_stop > self.current_stop) or (
                self.side == "short" and calculated_trail_stop < self.current_stop
            ):
                self.current_stop = calculated_trail_stop
                if not self.trail_step_2_triggered:
                    print(f"[{timestamp}] [TRAIL STEP 2] Macro Step activated at +50 ticks.")
                    self.trail_step_2_triggered = True

        # ---------------------------------------------------------------------
        # Order Fill Check Constraints (Stop / Target Intersections)
        # ---------------------------------------------------------------------
        if self.side == "long":
            if tick_price >= self.current_target:
                self.execute_exit(self.current_target, "PROFIT_TARGET_FILLED", timestamp)
            elif tick_price <= self.current_stop:
                self.execute_exit(self.current_stop, "STOP_LOSS_FILLED", timestamp)
        else:
            if tick_price <= self.current_target:
                self.execute_exit(self.current_target, "PROFIT_TARGET_FILLED", timestamp)
            elif tick_price >= self.current_stop:
                self.execute_exit(self.current_stop, "STOP_LOSS_FILLED", timestamp)

    def execute_exit(self, exit_price: float, reason: str, timestamp: str):
        self.exit_price = exit_price
        self.exit_reason = reason
        self.is_active = False

        # Calculate performance metrics
        if self.side == "long":
            realized_ticks = int((self.exit_price - self.entry_price) / 0.25)
        else:
            realized_ticks = int((self.entry_price - self.exit_price) / 0.25)

        realized_pnl = realized_ticks * self.tick_value

        # Calculate absolute execution regret (Hindsight delta vs optimal peak)
        regret_ticks = self.max_favorable_ticks - realized_ticks
        regret_dollar = regret_ticks * self.tick_value

        print("\n==============================================")
        print(f"[{timestamp}] [TRADE EXIT] Execution Block Terminated.")
        print(f"Reason: {self.exit_reason}")
        print(f"Exit Price: {self.exit_price:.2f}")
        print(f"Realized Performance: {realized_ticks} ticks (${realized_pnl:,.2f})")
        print(f"Peak Favorable Run: {self.max_favorable_ticks} ticks")
        print(f"Hindsight Dynamic Regret: {regret_ticks} ticks (${regret_dollar:,.2f})")
        print("==============================================\n")

    def to_report(self) -> dict:
        return {
            "entry_price": self.entry_price,
            "side": self.side,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "max_favorable_ticks": self.max_favorable_ticks,
            "breakeven_triggered": self.breakeven_triggered,
            "trail_step_1_triggered": self.trail_step_1_triggered,
            "trail_step_2_triggered": self.trail_step_2_triggered,
        }


# --- Test Engine Routine Using Simulated High-Velocity Tick Stream ---
if __name__ == "__main__":
    print("[SIMULATOR] Launching MES_Safe_Adjust ATM Backtest...")

    # Simulate entering long on NQ/MES at an arbitrary base level of 6474.25
    simulator = MESSafeAdjustSimulator(initial_entry_price=6474.25, side="long")

    # Simulated incoming tick feed passing through the strategy bounds
    mock_tick_stream = [
        ("09:30:01", 6474.50),  # +1 tick
        ("09:31:12", 6476.75),  # +10 ticks -> Triggers manual stop adjustment to +2 ticks
        ("09:32:05", 6473.00),  # Pullback checks if tightened manual stop holds (it does)
        ("09:33:40", 6478.25),  # +16 ticks -> Triggers target compression to +20 ticks
        ("09:34:10", 6479.25),  # +20 ticks -> Profit target intersection!
        ("09:34:11", 6481.00),  # Next market tick
    ]

    for timestamp, price in mock_tick_stream:
        if simulator.is_active:
            simulator.process_tick(price, timestamp)

    print(json.dumps(simulator.to_report(), indent=2))