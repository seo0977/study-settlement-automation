"""
study-settlement-automation
----------------------------
CPA 스터디그룹의 주간 공부시간 기록을 기반으로
개인별 벌금 잔액을 누적(이월)시키다가, 최종 정산 시점에
한 번에 벌금 pot을 상금 자격자들에게 분배하는 구조.

기존 수기 정산 방식:
- 매주 벌금을 걷어서 즉시 분배하지 않음
- 개인별로 "기초잔액 + 이번주 변동 = 기말잔액" 형태로 누적
- 최종 정산 시점에 모인 벌금(pot)을 그동안 상금 자격을 만족했던
  주차 수에 비례하여 나눠줌

Rules
-----
- 기준 시간 미달 시: 부족한 시간 1시간당 1,000원 벌금 → 개인 잔액에 가산(이월)
- 상금 자격: 기준 시간 이상 달성 + (상점-벌점 합계) >= 0
- 최종 정산: 누적된 벌금 pot을 상금 자격 주차 수 비례로 분배
"""

from dataclasses import dataclass, field
import math


@dataclass
class MemberWeekInput:
    name: str
    study_hours: float
    merit_points: float = 0


@dataclass
class MemberLedger:
    name: str
    balance: int = 0                 # 누적 벌금 잔액 (+: 내야 할 돈)
    eligible_weeks: int = 0          # 상금 자격을 만족했던 누적 주차 수
    history: list = field(default_factory=list)   # 주차별 기록 (감사 추적용)


class SettlementLedger:
    """여러 주차에 걸쳐 개인별 잔액을 누적하는 원장"""

    def __init__(self, fine_per_hour: int = 1000):
        self.fine_per_hour = fine_per_hour
        self.members: dict[str, MemberLedger] = {}
        self.total_pot = 0            # 누적 벌금 총액 (아직 분배 안 된 pot)
        self.week_log = []

    def _get_member(self, name: str) -> MemberLedger:
        if name not in self.members:
            self.members[name] = MemberLedger(name=name)
        return self.members[name]

    def process_week(self, week_label: str, threshold_hours: float,
                      entries: list[MemberWeekInput]):
        """한 주차 데이터를 처리해서 개인별 잔액에 반영 (기초 → 기말)"""
        week_summary = []

        for e in entries:
            m = self._get_member(e.name)
            opening_balance = m.balance

            shortfall = max(0, threshold_hours - e.study_hours)
            fine = math.ceil(shortfall) * self.fine_per_hour

            meets_hours = e.study_hours >= threshold_hours
            meets_points = e.merit_points >= 0
            is_eligible = meets_hours and meets_points

            m.balance += fine                      # 벌금은 잔액에 가산 (이월)
            self.total_pot += fine                  # 그룹 전체 pot에도 누적
            if is_eligible:
                m.eligible_weeks += 1

            record = {
                "week": week_label,
                "name": e.name,
                "study_hours": round(e.study_hours, 2),
                "merit_points": e.merit_points,
                "shortfall_hours": round(shortfall, 2),
                "fine_this_week": fine,
                "eligible_this_week": is_eligible,
                "opening_balance": opening_balance,
                "closing_balance": m.balance,
            }
            m.history.append(record)
            week_summary.append(record)

        self.week_log.append({"week": week_label, "records": week_summary})
        return week_summary

    def week_report(self, week_label: str) -> str:
        """특정 주차의 기초/변동/기말 리포트"""
        entry = next((w for w in self.week_log if w["week"] == week_label), None)
        if not entry:
            return f"'{week_label}' 데이터 없음"

        lines = [f"[{week_label}] 정산 내역", ""]
        for r in entry["records"]:
            elig = "✅ 상금자격" if r["eligible_this_week"] else ""
            lines.append(
                f"- {r['name']}: {r['study_hours']}시간 (상벌점 {r['merit_points']:+g}) "
                f"→ 이번주 벌금 {r['fine_this_week']:,}원 {elig}\n"
                f"    기초 {r['opening_balance']:,}원 + 이번주 {r['fine_this_week']:,}원 "
                f"= 기말 {r['closing_balance']:,}원"
            )
        lines.append("")
        lines.append(f"누적 pot 총액: {self.total_pot:,}원")
        return "\n".join(lines)

    def final_settlement(self) -> dict:
        """
        최종 정산: 누적된 pot을 '상금 자격 주차 수' 비례로 분배하고,
        각자의 최종 순잔액(낼 돈 - 받을 돈)을 계산.
        """
        total_eligible_weeks = sum(m.eligible_weeks for m in self.members.values())
        result = []

        for m in self.members.values():
            if total_eligible_weeks > 0:
                payout = self.total_pot * (m.eligible_weeks / total_eligible_weeks)
            else:
                payout = 0
            net = round(m.balance - payout)  # 양수: 최종적으로 내야 할 돈 / 음수: 받을 돈
            result.append({
                "name": m.name,
                "fine_balance": m.balance,
                "eligible_weeks": m.eligible_weeks,
                "payout": round(payout),
                "net_settlement": net,
            })

        result.sort(key=lambda r: -r["net_settlement"])
        return {
            "total_pot": self.total_pot,
            "total_eligible_weeks": total_eligible_weeks,
            "members": result,
        }

    def final_report(self) -> str:
        data = self.final_settlement()
        lines = [f"===== 최종 정산 (누적 pot: {data['total_pot']:,}원) =====", ""]
        for r in data["members"]:
            if r["net_settlement"] > 0:
                verb = f"{r['net_settlement']:,}원 납부"
            elif r["net_settlement"] < 0:
                verb = f"{-r['net_settlement']:,}원 수령"
            else:
                verb = "정산 완료 (0원)"
            lines.append(
                f"- {r['name']}: 벌금누적 {r['fine_balance']:,}원 / "
                f"상금자격 {r['eligible_weeks']}주 / 분배 {r['payout']:,}원 → {verb}"
            )
        return "\n".join(lines)


if __name__ == "__main__":
    ledger = SettlementLedger(fine_per_hour=1000)

    # 샘플 데이터 (익명화). 실제로는 주차별로 반복 호출하면 됨.
    ledger.process_week(
        week_label="1주차",
        threshold_hours=55,
        entries=[
            MemberWeekInput("멤버A", study_hours=58.0, merit_points=1),
            MemberWeekInput("멤버B", study_hours=50.0, merit_points=-1),
            MemberWeekInput("멤버C", study_hours=60.0, merit_points=0),
        ],
    )
    ledger.process_week(
        week_label="2주차 (기준상향)",
        threshold_hours=62,
        entries=[
            MemberWeekInput("멤버A", study_hours=61.5, merit_points=3),
            MemberWeekInput("멤버B", study_hours=58.0, merit_points=-2),
            MemberWeekInput("멤버C", study_hours=64.2, merit_points=0),
        ],
    )

    print(ledger.week_report("1주차"))
    print()
    print(ledger.week_report("2주차 (기준상향)"))
    print()
    print(ledger.final_report())
