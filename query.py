"""
query.py
--------
SettlementLedger 결과를 자연어 질의로 조회하는 간단한 규칙 기반 파서.

지금은 키워드 매칭 기반이지만, 인터페이스를 answer_question(ledger, question)
하나로 고정해뒀기 때문에 추후 LLM 기반 파서로 교체해도
호출부(CLI, 챗봇 등)는 수정할 필요가 없도록 설계했습니다.
(TODO: 실제 LLM 연동은 다음 단계로 남겨둠 — README 참고)
"""

import re
from settlement import SettlementLedger


def answer_question(ledger: SettlementLedger, question: str) -> str:
    q = question.strip()

    # 1) 특정 주차 벌금/상금 총액
    m = re.search(r"(\d+)\s*주차?\s*(벌금|상금)", q)
    if m:
        week_num, kind = m.group(1), m.group(2)
        week_label = f"Week {week_num}"
        entry = next((w for w in ledger.week_log
                      if w.get("week") == week_label and "records" in w), None)
        if not entry:
            return f"'{week_label}' 데이터를 찾을 수 없습니다."
        if kind == "벌금":
            return f"{week_label} 벌금 총액: {entry['total_fine']:,}원 (자격자 {entry['eligible_count']}명)"
        else:
            return f"{week_label} 1인당 상금: {entry['prize_per_person']:,}원"

    # 2) 특정 멤버 잔액 조회
    m = re.search(r"(Member\d+|[가-힣]+)\s*(잔액|보증금)", q)
    if m:
        name = m.group(1)
        member = ledger.members.get(name)
        if not member:
            return f"'{name}' 멤버를 찾을 수 없습니다."
        status = "활동중" if member.active else "탈퇴"
        return f"{name} ({status}): 현재 잔액 {member.balance:,.0f}원"

    # 3) 특정 주차 자격자 명단
    m = re.search(r"(\d+)\s*주차?\s*자격자", q)
    if m:
        week_label = f"Week {m.group(1)}"
        entry = next((w for w in ledger.week_log
                      if w.get("week") == week_label and "records" in w), None)
        if not entry:
            return f"'{week_label}' 데이터를 찾을 수 없습니다."
        eligible = [r["name"] for r in entry["records"] if r["eligible"]]
        return f"{week_label} 자격자 ({len(eligible)}명): {', '.join(eligible)}"

    # 4) 탈퇴자 조회
    if "탈퇴" in q:
        withdrawals = [w for w in ledger.week_log if w.get("event") == "withdrawal"]
        if not withdrawals:
            return "탈퇴한 멤버가 없습니다."
        return "\n".join(
            f"- {w['who']}: {w['week']} 탈퇴, 잔액 {w['forfeited']:,}원 잔존 인원에게 분배"
            for w in withdrawals
        )

    # 5) 최종 정산 요약
    if "최종" in q and ("정산" in q or "잔액" in q):
        return ledger.final_report()

    return (
        "이해하지 못한 질문입니다. 예시:\n"
        "- '2주차 벌금 얼마야'\n"
        "- 'Member1 잔액 알려줘'\n"
        "- '1주차 자격자 누구야'\n"
        "- '탈퇴자 있어?'\n"
        "- '최종 정산 결과 보여줘'"
    )


if __name__ == "__main__":
    from settlement import SettlementLedger, MemberWeekInput

    ledger = SettlementLedger()
    ledger.process_week("Week 1", 55, [
        MemberWeekInput("Member1", 61.05, 2),
        MemberWeekInput("Member2", 50.07, -0.5),
    ])

    for q in ["1주차 벌금 얼마야", "Member1 잔액 알려줘", "탈퇴자 있어?"]:
        print(f"Q: {q}")
        print(f"A: {answer_question(ledger, q)}\n")
