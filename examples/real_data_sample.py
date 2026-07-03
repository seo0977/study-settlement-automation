"""
examples/real_data_sample.py
-----------------------------
실제 스터디 운영 기록(3개 주차)을 익명 처리하여 settlement.py 로직을
검증하는 예시입니다. 이름은 모두 Member1~Member9로 치환했습니다.

기준 시간이 학기 초 55시간 → 시험 임박 후 62시간으로 상향된 것도
실제 운영 방식 그대로 반영했습니다.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settlement import SettlementLedger, MemberWeekInput  # noqa: E402


ledger = SettlementLedger(fine_per_hour=1000)

# ---- Week 1 (threshold 55h) ----
ledger.process_week(
    week_label="Week 1",
    threshold_hours=55,
    entries=[
        MemberWeekInput("Member1", study_hours=61.08, merit_points=2),
        MemberWeekInput("Member2", study_hours=50.07, merit_points=-0.5),
        MemberWeekInput("Member3", study_hours=48.07, merit_points=2),
        MemberWeekInput("Member4", study_hours=61.18, merit_points=1),
        MemberWeekInput("Member5", study_hours=64.77, merit_points=6),
        MemberWeekInput("Member6", study_hours=57.78, merit_points=6),
        MemberWeekInput("Member7", study_hours=51.70, merit_points=0),
        MemberWeekInput("Member8", study_hours=61.55, merit_points=5),
        MemberWeekInput("Member9", study_hours=60.32, merit_points=11.5),
    ],
)

# ---- Week 2 (threshold raised to 62h ahead of exam) ----
ledger.process_week(
    week_label="Week 2",
    threshold_hours=62,
    entries=[
        MemberWeekInput("Member1", study_hours=68.22, merit_points=5),
        MemberWeekInput("Member2", study_hours=63.02, merit_points=5),
        MemberWeekInput("Member3", study_hours=53.22, merit_points=3),
        MemberWeekInput("Member4", study_hours=64.22, merit_points=4),
        MemberWeekInput("Member5", study_hours=70.10, merit_points=4),
        MemberWeekInput("Member6", study_hours=52.90, merit_points=-1),
        MemberWeekInput("Member7", study_hours=64.27, merit_points=5),
        MemberWeekInput("Member8", study_hours=66.47, merit_points=5),
        MemberWeekInput("Member9", study_hours=51.28, merit_points=-4.5),
    ],
)

# ---- Week 3 (threshold 62h) ----
ledger.process_week(
    week_label="Week 3",
    threshold_hours=62,
    entries=[
        MemberWeekInput("Member1", study_hours=68.72, merit_points=7.5),
        MemberWeekInput("Member2", study_hours=61.55, merit_points=1.5),
        MemberWeekInput("Member3", study_hours=47.87, merit_points=-1),
        MemberWeekInput("Member4", study_hours=57.33, merit_points=5),
        MemberWeekInput("Member5", study_hours=67.67, merit_points=4),
        MemberWeekInput("Member6", study_hours=63.13, merit_points=1),
        MemberWeekInput("Member7", study_hours=60.98, merit_points=-2.5),
        MemberWeekInput("Member8", study_hours=63.07, merit_points=3),
        MemberWeekInput("Member9", study_hours=56.20, merit_points=6),
    ],
)

if __name__ == "__main__":
    for week in ["Week 1", "Week 2", "Week 3"]:
        print(ledger.week_report(week))
        print()

    print(ledger.final_report())
