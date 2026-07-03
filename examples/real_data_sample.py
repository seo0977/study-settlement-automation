"""
examples/real_data_sample.py
-----------------------------
실제 정산 시트(4월 1주, 4월 4주)의 공부시간·상벌점 기록을 익명화하여
settlement.py 로직을 검증합니다. 이름은 Member1~9로 치환했습니다.

주의: 이 스크립트는 두 주 모두 전원 보증금 10,000원부터 새로 시작하는
것으로 가정합니다. 실제 시트에서는 이전 주차부터 누적된 잔액이 있어
기초/기말 절대값은 실제 시트와 다르지만, 각 주의 벌금/상금 "변동액"은
실제 시트에 기록된 값과 정확히 일치합니다 (예: 자격 미달+벌점 인원의
벌금액, 자격자 1인당 상금액 등).

또한 실제로 발생했던 중도탈퇴 상황(보증금 반납 없이 잔존 인원에게 재분배)도
같은 방식으로 재현했습니다.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settlement import SettlementLedger, MemberWeekInput  # noqa: E402


ledger = SettlementLedger(initial_deposit=10000, fine_per_point=1000)

# ---- Week 1 (실제: 4월 1주, 기준 55시간) ----
# 검증: 벌금/상금 변동액이 실제 시트 기록과 일치 (예: 미달+벌점 인원 -500원,
# 자격자 1인당 +100원)
ledger.process_week(
    week_label="Week 1",
    threshold_hours=55,
    entries=[
        MemberWeekInput("Member1", study_hours=0.0, merit_points=0),
        MemberWeekInput("Member2", study_hours=25.27, merit_points=2),
        MemberWeekInput("Member3", study_hours=45.45, merit_points=0.5),
        MemberWeekInput("Member4", study_hours=66.97, merit_points=11),
        MemberWeekInput("Member5", study_hours=69.08, merit_points=9),
        MemberWeekInput("Member6", study_hours=63.02, merit_points=12),
        MemberWeekInput("Member7", study_hours=47.98, merit_points=-0.5),
        MemberWeekInput("Member8", study_hours=56.97, merit_points=3),
        MemberWeekInput("Member9", study_hours=57.85, merit_points=0),
    ],
)

# ---- Week 2 (실제: 4월 4주, 기준 55시간) ----
# 검증: 벌금/상금 변동액이 실제 시트 기록과 일치 (예: -1,500원, -3,500원,
# 자격자 1인당 +1,250원)
ledger.process_week(
    week_label="Week 2",
    threshold_hours=55,
    entries=[
        MemberWeekInput("Member1", study_hours=51.02, merit_points=-1.5),
        MemberWeekInput("Member2", study_hours=55.0, merit_points=0.0),
        MemberWeekInput("Member3", study_hours=47.53, merit_points=1.5),
        MemberWeekInput("Member4", study_hours=60.68, merit_points=0.5),
        MemberWeekInput("Member5", study_hours=67.4, merit_points=8.0),
        MemberWeekInput("Member6", study_hours=31.85, merit_points=-3.5),
        MemberWeekInput("Member7", study_hours=51.05, merit_points=0.5),
        MemberWeekInput("Member8", study_hours=62.97, merit_points=6.0),
        MemberWeekInput("Member9", study_hours=48.62, merit_points=6.5),
    ],
)

# ---- 중도탈퇴 시연 ----
# 실제로 발생했던 상황(팀원 탈퇴, 보증금 반납 없이 잔존 인원에게 재분배)을
# 같은 메커니즘으로 재현합니다.
withdrawal_result = ledger.withdraw("Member2", week_label="Week 2 이후 탈퇴")


if __name__ == "__main__":
    print(ledger.week_report("Week 1"))
    print()
    print(ledger.week_report("Week 2"))
    print()
    print(
        f"[중도탈퇴] Member2 잔액 {withdrawal_result['forfeited']:,}원 몰수 → "
        f"잔존 {ledger.week_log[-1]['remaining_count']}명에게 "
        f"{withdrawal_result['share_per_remaining']:,}원씩 분배"
    )
    print()
    print(ledger.final_report())
