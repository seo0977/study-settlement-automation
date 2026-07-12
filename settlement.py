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
- 그 주 걷힌 벌금 총액을 그 주 자격자들끼리 1/n 하여 잔액에 가산
  (정수 나눗셈 후 나머지는 이름순으로 1원씩 우선 배분 → 총액 100% 보존)
- 중도탈퇴 시 보증금 반납 없음: 탈퇴자의 기말잔액 전액을 잔존 인원에게 동일하게 분배
  (마찬가지로 나머지는 이름순 1원씩 배분)
- 잔액이 마이너스가 되어도 자동 충전 없음 — 빚처럼 누적되다가 최종 정산 시 방장이
  기말잔액만큼 입금/회수. (추가 보증금 납부는 실제로 입금됐을 때만 add_deposit으로 기록)
- 멤버는 register_member()로 명시 등록 후에만 정산 대상이 됩니다.
  (오타로 인한 유령 멤버 생성을 막기 위함)
"""

from dataclasses import dataclass


@dataclass
class MemberWeekInput:
    name: str
    study_hours: float
    merit_points: float = 0


@dataclass
class Member:
    name: str
    balance: int = 10000
    active: bool = True


def _distribute_with_remainder(total: int, names: list[str]) -> dict[str, int]:
    """
    total원을 names 인원에게 최대한 균등하게 나누되, 나머지(원 단위)는
    이름순으로 정렬한 뒤 앞에서부터 1원씩 배분해 총액을 정확히 보존합니다.

    예: 500원을 6명에게 → 1인당 83원(498원) + 나머지 2원을
        이름순 앞 2명에게 1원씩 추가 → 정확히 500원 분배.
    """
    if not names:
        return {}
    base = total // len(names)
    remainder = total - base * len(names)
    sorted_names = sorted(names)
    result = {name: base for name in names}
    for name in sorted_names[:remainder]:
        result[name] += 1
    return result


class SettlementLedger:
    def __init__(self, initial_deposit: int = 10000, fine_per_point: int = 1000):
        self.initial_deposit = initial_deposit
        self.fine_per_point = fine_per_point
        self.members: dict[str, Member] = {}
        self.week_log = []

    def register_member(self, name: str):
        """
        정산 대상 멤버를 명시적으로 등록합니다.
        등록되지 않은 이름이 CSV/입력에 들어오면 오타로 판단해 에러를 냅니다.
        """
        if name in self.members:
            raise ValueError(f"'{name}'은(는) 이미 등록된 멤버입니다.")
        self.members[name] = Member(name=name, balance=self.initial_deposit)

    def _get_registered(self, name: str) -> Member:
        if name not in self.members:
            raise ValueError(
                f"'{name}'은(는) 등록되지 않은 멤버입니다. "
                f"오타이거나 register_member()로 먼저 등록해야 합니다."
            )
        return self.members[name]

    def add_deposit(self, name: str, amount: int):
        """실제로 추가 보증금이 입금됐을 때만 수동으로 기록."""
        if amount <= 0:
            raise ValueError("add_deposit은 양수 금액만 허용합니다.")
        m = self._get_registered(name)
        m.balance += amount

    def process_week(self, week_label: str, threshold_hours: float,
                      entries: list[MemberWeekInput]):
        eligible_names = []
        fine_records = {}
        total_fine = 0

        # 0단계: 입력 검증 + 등록 확인
        for e in entries:
            if e.study_hours < 0:
                raise ValueError(f"{e.name}: study_hours는 음수일 수 없습니다.")
            self._get_registered(e.name)  # 미등록이면 여기서 에러

        # 1단계: 자격 판정 + 벌금 계산
        for e in entries:
            m = self.members[e.name]
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

        # 2단계: 벌금 pool을 자격자끼리 정확히 분배 (나머지 원 유실 없음)
        prize_map = _distribute_with_remainder(total_fine, eligible_names)

        # 3단계: 잔액 반영
        week_records = []
        for e in entries:
            m = self.members[e.name]
            if not m.active:
                continue
            opening = m.balance
            change = prize_map[e.name] if e.name in eligible_names else fine_records[e.name]
            m.balance += change
            record = {
                "week": week_label, "name": e.name,
                "study_hours": round(e.study_hours, 2),
                "merit_points": e.merit_points,
                "eligible": e.name in eligible_names,
                "change": change,
                "opening_balance": opening,
                "closing_balance": m.balance,
            }
            week_records.append(record)

        self.week_log.append({
            "week": week_label, "total_fine": total_fine,
            "eligible_count": len(eligible_names),
            "records": week_records,
        })
        return week_records

    def withdraw(self, name: str, week_label: str = "탈퇴"):
        """중도탈퇴 처리: 보증금 반납 없음, 잔액 전액을 잔존 인원에게 정확히 분배"""
        m = self._get_registered(name)
        if not m.active:
            raise ValueError(f"'{name}'은(는) 이미 탈퇴 처리된 멤버입니다.")

        forfeited = m.balance
        m.balance = 0
        m.active = False

        remaining_names = [mm.name for mm in self.members.values() if mm.active]
        share_map = _distribute_with_remainder(forfeited, remaining_names)
        for name_, share in share_map.items():
            self.members[name_].balance += share

        self.week_log.append({
            "week": week_label, "event": "withdrawal", "who": name,
            "forfeited": forfeited, "remaining_count": len(remaining_names),
        })
        return {"forfeited": forfeited, "share_map": share_map}

    def week_report(self, week_label: str) -> str:
        entry = next((w for w in self.week_log if w.get("week") == week_label
                       and "records" in w), None)
        if not entry:
            return f"'{week_label}' 데이터 없음"
        lines = [
            f"[{week_label}] 벌금 총액 {entry['total_fine']:,}원 / "
            f"자격자 {entry['eligible_count']}명",
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
        result = []
        for m in self.members.values():
            net_vs_deposit = m.balance - self.initial_deposit
            result.append({
                "name": m.name, "active": m.active,
                "final_balance": m.balance, "net_vs_deposit": net_vs_deposit,
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

    for name in ["Member1", "Member2", "Member3", "Member4", "Member5",
                 "Member6", "Member7", "Member8", "Member9"]:
        ledger.register_member(name)

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
