"""
study-settlement-automation
----------------------------
CPA 스터디그룹의 주간 공부시간/상벌점 기록을 기반으로,
멤버별 보증금 잔액을 매주 정산·누적하는 원장(ledger) 스크립트.

실제 운영 규칙 (방장 인계 이후 도입)
------------------------------------
- 전원 보증금 10,000원으로 시작 (기초잔액)
- 매주 자격 판정: 기준시간(기본 55시간, 시험 임박 시 방장 재량으로 임시 상향) 이상
  달성 + 상벌점 합계 0 이상 → 그 주 "자격자"
- 자격 없음 + 상벌점 마이너스 → 그 주 벌금 = |상벌점| x 1,000원, 잔액에서 즉시 차감
- 자격 없음 + 상벌점 0 이상 (시간만 미달) → 벌금 없음, 잔액 변동 없음
- 그 주 걷힌 벌금 총액을 그 주 자격자들끼리 1/n 하여 잔액에 가산 (반올림)
- 중도탈퇴 시 보증금 반납 없음: 탈퇴자의 기말잔액 전액을 잔존 인원에게 1/n 가산 (반올림)
- 잔액이 마이너스가 되어도 자동 충전 없음 — 빚처럼 누적되다가 최종 정산 시 방장이
  기말잔액만큼 입금/회수. (추가 보증금 납부는 실제로 입금됐을 때만 add_deposit으로 기록)
"""

from dataclasses import dataclass, field


@dataclass
class MemberWeekInput:
    name: str
    study_hours: float
    merit_points: float = 0


@dataclass
class Member:
    name: str
    balance: float = 10000
    active: bool = True
    history: list = field(default_factory=list)


class SettlementLedger:
    def __init__(self, initial_deposit: float = 10000, fine_per_point: int = 1000):
        self.initial_deposit = initial_deposit
        self.fine_per_point = fine_per_point
        self.members: dict[str, Member] = {}
        self.week_log = []

    def _get_or_create(self, name: str) -> Member:
        if name not in self.members:
            self.members[name] = Member(name=name, balance=self.initial_deposit)
        return self.members[name]

    def add_deposit(self, name: str, amount: float, note: str = ""):
        """실제로 추가 보증금이 입금됐을 때만 수동으로 기록"""
        m = self._get_or_create(name)
        m.balance += amount
        m.history.append({"event": "deposit", "amount": amount, "note": note,
                           "balance_after": m.balance})

    def process_week(self, week_label: str, threshold_hours: float,
                      entries: list[MemberWeekInput]):
        eligible_names = []
        fine_records = {}
        total_fine = 0

        # 1단계: 자격 판정 + 벌금 계산
        for e in entries:
            m = self._get_or_create(e.name)
            if not m.active:
                continue
            is_eligible = (e.study_hours >= threshold_hours) and (e.merit_points >= 0)
            if is_eligible:
                eligible_names.append(e.name)
                fine_records[e.name] = 0
            elif e.merit_points < 0:
                fine = round(abs(e.merit_points) * self.fine_per_point)
                fine_records[e.name] = -fine
                total_fine += fine
            else:
                fine_records[e.name] = 0  # 시간만 미달, 벌금 없음

        # 2단계: 이번 주 벌금 pool을 자격자끼리 1/n (반올림)
        prize_per_person = round(total_fine / len(eligible_names)) if eligible_names else 0

        # 3단계: 잔액 반영
        week_records = []
        for e in entries:
            m = self.members[e.name]
            if not m.active:
                continue
            opening = m.balance
            change = prize_per_person if e.name in eligible_names else fine_records[e.name]
            m.balance += change
            record = {
                "week": week_label, "name": e.name,
                "study_hours": round(e.study_hours, 2),
                "merit_points": e.merit_points,
                "eligible": e.name in eligible_names,
                "change": change,
                "opening_balance": round(opening),
                "closing_balance": round(m.balance),
            }
            m.history.append(record)
            week_records.append(record)

        self.week_log.append({
            "week": week_label, "total_fine": total_fine,
            "eligible_count": len(eligible_names),
            "prize_per_person": prize_per_person,
            "records": week_records,
        })
        return week_records

    def withdraw(self, name: str, week_label: str = "탈퇴"):
        """중도탈퇴 처리: 보증금 반납 없음, 잔액 전액을 잔존 인원에게 1/n"""
        m = self.members[name]
        forfeited = m.balance
        m.balance = 0
        m.active = False

        remaining = [mm for mm in self.members.values() if mm.active]
        share = round(forfeited / len(remaining)) if remaining else 0
        for r in remaining:
            r.balance += share
        self.week_log.append({
            "week": week_label, "event": "withdrawal", "who": name,
            "forfeited": round(forfeited), "share_per_remaining": share,
            "remaining_count": len(remaining),
        })
        return {"forfeited": round(forfeited), "share_per_remaining": share}

    def week_report(self, week_label: str) -> str:
        entry = next((w for w in self.week_log if w.get("week") == week_label
                       and "records" in w), None)
        if not entry:
            return f"'{week_label}' 데이터 없음"
        lines = [
            f"[{week_label}] 벌금 총액 {entry['total_fine']:,}원 / "
            f"자격자 {entry['eligible_count']}명 / 1인당 상금 {entry['prize_per_person']:,}원",
            "",
        ]
        for r in entry["records"]:
            tag = "✅자격" if r["eligible"] else ""
            sign = f"+{r['change']:,}" if r["change"] >= 0 else f"{r['change']:,}"
            lines.append(
                f"- {r['name']}: {r['study_hours']}h (상벌점 {r['merit_points']:+g}) {tag} "
                f"→ {sign}원 (기초 {r['opening_balance']:,} → 기말 {r['closing_balance']:,})"
            )
        return "\n".join(lines)

    def final_settlement(self) -> dict:
        """최종 정산: 방장이 각자 기말잔액만큼 돌려주면(혹은 회수하면) 끝"""
        result = []
        for m in self.members.values():
            net_vs_deposit = round(m.balance - self.initial_deposit)
            result.append({
                "name": m.name,
                "active": m.active,
                "final_balance": round(m.balance),
                "net_vs_deposit": net_vs_deposit,  # +면 처음 보증금보다 이득, -면 손해
            })
        result.sort(key=lambda r: -r["final_balance"])
        return result

    def final_report(self) -> str:
        data = self.final_settlement()
        lines = ["===== 최종 정산 (기말잔액 = 방장이 돌려줄 금액) =====", ""]
        for r in data:
            status = "" if r["active"] else " (중도탈퇴)"
            diff = f"+{r['net_vs_deposit']:,}" if r["net_vs_deposit"] >= 0 else f"{r['net_vs_deposit']:,}"
            lines.append(
                f"- {r['name']}{status}: 기말잔액 {r['final_balance']:,}원 "
                f"(보증금 대비 {diff}원)"
            )
        return "\n".join(lines)


if __name__ == "__main__":
    ledger = SettlementLedger(initial_deposit=10000, fine_per_point=1000)

    ledger.process_week(
        week_label="Week 1",
        threshold_hours=55,
        entries=[
            MemberWeekInput("Member1", study_hours=61.05, merit_points=2),
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

    # Week 2: Member2가 중도탈퇴
    ledger.process_week(
        week_label="Week 2",
        threshold_hours=55,
        entries=[
            MemberWeekInput("Member1", study_hours=47.6, merit_points=1.0),
            MemberWeekInput("Member3", study_hours=50.13, merit_points=1),
            MemberWeekInput("Member4", study_hours=63.95, merit_points=2),
            MemberWeekInput("Member5", study_hours=70.57, merit_points=4),
            MemberWeekInput("Member6", study_hours=65.32, merit_points=3),
            MemberWeekInput("Member7", study_hours=57.82, merit_points=3),
            MemberWeekInput("Member8", study_hours=60.4, merit_points=3),
            MemberWeekInput("Member9", study_hours=63.2, merit_points=6),
        ],
    )
    ledger.withdraw("Member2", week_label="Week 2 탈퇴")

    print(ledger.week_report("Week 1"))
    print()
    print(ledger.week_report("Week 2"))
    print()
    print(ledger.final_report())
