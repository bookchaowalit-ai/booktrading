---
title: BookFinance — Software Requirements (SRS)
doc_id: BTR-DOC-05
doc_type: srs
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: BA (Book Dev)
related: 01-prd.md, 02-architecture.md, 06-ux-flows.md, 07-test-uat.md, 08-rtm.md
---

# BookFinance — Software Requirements (SRS)

## 1. บทบาทและสิทธิ์

| บทบาท | ที่มา | อ่าน | เขียน |
|---|---|---|---|
| public | ไม่ login | `/api/health`, `/api/auth/*` บางส่วน, landing | — |
| user | login แล้ว | dashboard และ route ระดับ user | route ที่เป็น `userRule` |
| admin | ผู้ใช้ admin (`FIRST_ADMIN_*`) | ทุกอย่าง | route admin รวม write ผ่าน `/strategy-api`, reset kill switch, real-grid kill/enable |
| service | strategy service ด้วย `AUTH_TOKEN` | route ที่เป็น `serviceRule` | ตามที่ `route_access.go` อนุญาต |

แหล่งความจริงของสิทธิ์ต่อ route คือ `backend/internal/adapter/http/route_access.go` และ `strategy/tests/test_route_access_matrix.py`

## 2. Use case / user story

| ID | Story | Acceptance criteria |
|---|---|---|
| US-01 | ในฐานะ operator ฉันต้องการเห็นว่า "วันนี้ควรทำอะไร" | หน้า Today แสดง decision, สถานะ kill switch, ทุน และ trigger ถัดไปจาก `/api/command-center`; ไม่มีปุ่ม Start/Trade |
| US-02 | ในฐานะ operator ฉันต้องการดูว่าเกิดอะไรขึ้น | หน้า Evidence แสดง timeline, gate checklist, paper positions, activity feed |
| US-03 | ในฐานะ operator ฉันต้องการดูสิ่งที่ควรเฝ้าดู | หน้า Research แสดง crypto candidates, Polymarket reviews, market intel |
| US-04 | ในฐานะ operator ฉันต้องการรู้ว่าระบบยังดีอยู่ไหม | หน้า System แสดง health ของ component และ risk source แยก paper_bot กับ grid; refresh ทุก 30 วินาที |
| US-05 | ในฐานะ operator ฉันต้องการสรุปรายวัน | หน้า Daily Report แสดง journal summary, daily PnL, ภาพรวมระบบ |
| US-06 | ในฐานะเจ้าของทุน ฉันต้องการให้ระบบหยุดเองเมื่อขาดทุนเกินเกณฑ์ | เมื่อ paper drawdown > 5% หรือขาดทุนต่อเนื่อง 3 ครั้ง หรือขาดทุนรายวันเกิน $5 หรือ API ล้มเหลวต่อเนื่อง 3 ครั้ง kill switch ACTIVE (`strategy/app/polymarket/paper_bot.py`) และไม่มี entry ใหม่ |
| US-07 | ในฐานะเจ้าของทุน ฉันต้องการให้การ reset kill switch ทำได้เฉพาะผู้มีสิทธิ์ | `POST /api/poly-paper/reset-kill-switch` โดยไม่ auth ได้ 401/403 |
| US-08 | ในฐานะ operator ฉันต้องการทดลอง futures โดยไม่เสี่ยงเงินจริง | `FUTURES_EXECUTION_MODE` รับเฉพาะ `paper`/`testnet`; mainnet ถูกปฏิเสธ; preflight ไม่ส่ง order |
| US-09 | ในฐานะ operator ฉันต้องการ backtest อย่างซื่อตรง | backtest แยก in-sample/out-of-sample, คิด fee/slippage/funding, ไม่ optimize parameter |
| US-10 | ในฐานะ admin ฉันต้องการ login อย่างปลอดภัย | lock ต่อ (email, IP) หลังพยายามผิดหลายครั้ง; registration ปิดได้หรือต้องมี invite code |
| US-11 | ในฐานะ operator ฉันต้องการ monitor แบบ CLI | `scripts/monitor.py` พิมพ์ decision block ตาม decision tree |

## 3. Functional requirements

| ID | Requirement | Priority | Phase | สถานะ |
|---|---|---|---|---|
| FR-01 | `GET /api/command-center` คืน decision, kill switch (source `paper_bot`), capital, next triggers และหน้า Today แสดงผล | Must | P0 | มีแล้ว |
| FR-02 | `GET /api/evidence` + หน้า Evidence (timeline, gates, positions, activity) | Must | P0 | มีแล้ว |
| FR-03 | Research: `/api/research`, `/api/market-intel/*`, `/api/signal-tracker/*`; scan เป็น POST ที่ต้อง auth | Should | P0 | มีแล้ว |
| FR-04 | System health: `/api/health`, `/api/risk/status`, `/api/real-grid/health` + หน้า System | Should | P0 | มีแล้ว |
| FR-05 | Daily report: `/api/report/daily` + หน้า Daily Report | Should | P0 | มีแล้ว |
| FR-06 | Kill switch อัตโนมัติตาม drawdown/daily loss/consecutive loss และ reset ต้อง auth | Must | P0 | มีแล้ว |
| FR-07 | Dry-run (`POLY_DRY_RUN=true`), safety filters, blocklist/allowlist; ค่าเริ่มต้นไม่ใช่ mainnet | Must | P0 | มีแล้ว |
| FR-08 | Paper engines: grid 5 คู่, DCA, Polymarket paper bot, arbitrage paper bot | Should | P0 | มีแล้ว |
| FR-09 | Futures USDⓈ-M paper/testnet + `GET /api/futures/preflight`; ปฏิเสธ mainnet; leverage ≤ 5x | Could | P0 | มีแล้ว |
| FR-10 | Backtest: `/api/backtest`, `/compare`, `/sweep`, `/walk-forward` และ `scripts/futures_backtest.py` | Should | P0 | มีแล้ว |
| FR-11 | Auth: login/logout/me, lockout, registration gated, roles | Must | P0 | มีแล้ว |
| FR-12 | Proxy `/strategy-api` ตรวจ session, เติม `AUTH_TOKEN` ฝั่ง server, write เป็น admin | Must | P0 | มีแล้ว |
| FR-13 | หน้า action-heavy ซ่อนหลัง `NEXT_PUBLIC_ADVANCED_UI=true` | Must | P0 | มีแล้ว |
| FR-14 | `scripts/monitor.py` decision tree (WAIT → REVIEW_SIGNALS → ENABLE_DRY_RUN → RESET_PAPER → MICRO-LIVE) | Must | P0 | มีแล้ว |
| FR-15 | UI สองภาษา TH/EN ผ่าน route `/[lang]` | Should | P0 | มีแล้ว |
| FR-16 | Finance module: `/api/finance/*` (dashboard, net worth, accounts, transactions, categories, budgets) แยกสิทธิ์ต่อเจ้าของข้อมูล | Could | P0 | มี API; การใช้งานจริง **[ต้องยืนยัน]** |
| FR-17 | Exchange integration: balance/ticker/order ผ่าน `/api/trade/*`, `/api/exchange/*`; order ที่ผลไม่ชัดต้อง reconcile | Could | P3 | มี adapter; เงินจริงถูกบล็อก |
| FR-18 | Notifications: `/api/notifications`, Telegram bot, webhook kill-switch alert | Could | P0 | มีโค้ด; การเปิดใช้ **[ต้องยืนยัน]** |

## 4. ข้อจำกัดและกฎ

| ID | กฎ | ที่มา |
|---|---|---|
| BR-01 | ห้ามใช้เงินจริงจนกว่า micro-live prerequisites ครบ | `strategy/RUNBOOK.md` §Rules |
| BR-02 | ห้าม reset kill switch ถ้า active positions > 8 หรือยังไม่ทบทวน per-signal PnL | `strategy/RUNBOOK.md` |
| BR-03 | ใช้ `paper_bot` เป็น risk source ของ gate; grid risk แยกต่างหาก | `docs/READINESS_CHECKLIST.md` |
| BR-04 | จำนวน position สูงสุด 8 | `strategy/RUNBOOK.md` §System State |

## การอนุมัติ

| บทบาท | สถานะ | วันที่ | ลงนาม |
|---|---|---|---|
| BA (Book Dev) | รอตรวจ | — | [ต้องยืนยัน] |
| Product owner | รอตรวจ | — | [ต้องยืนยัน] |

## แหล่งข้อมูล

- `strategy/infrastructure/api/app.py` (route ของ strategy)
- `backend/internal/adapter/http/handler.go`, `trade_handler.go`, `route_access.go`, `strategy_proxy.go`, `auth_handler.go`
- `frontend/src/app/[lang]/dashboard/`, `frontend/src/components/Sidebar.tsx`
- `strategy/RUNBOOK.md`, `docs/READINESS_CHECKLIST.md`, `README.md`
