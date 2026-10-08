---
title: BookFinance — ภาพรวมระบบและสารบัญเอกสาร
doc_id: BTR-DOC-00
doc_type: overview
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: Product owner (Book Dev)
related: 00-product-card.md, 01-prd.md, 02-architecture.md, 03-nfr-security.md, 04-runbook.md, 05-srs.md, 06-ux-flows.md, 07-test-uat.md, 08-rtm.md
---

# BookFinance — ภาพรวมระบบและสารบัญเอกสาร

## 1. สรุประบบ

BookFinance (repo `booktrading`) เป็นศูนย์บัญชาการการเงินสำหรับผู้ใช้คนเดียวที่ทำ paper trading คริปโตและ prediction market (Polymarket) ระบบประกอบด้วย backend Go (HTTP/WebSocket/gRPC), strategy service Python (FastAPI: กลยุทธ์ grid/DCA/futures/arbitrage, ตัวพยากรณ์, Polymarket paper bot, market intel) และ frontend Next.js 15.5 / React 19 ที่อ่าน `/api/command-center` เป็นแหล่งความจริงเดียว หัวใจของผลิตภัณฑ์คือ **การปกป้องทุน**: ค่าเริ่มต้นเป็น observe-only, มี kill switch, `POLY_DRY_RUN=true` และ readiness gate 5 ขั้นที่ต้องมีหลักฐานก่อนจะใช้เงินจริง

## 2. สถานะปัจจุบัน

| หัวข้อ | สถานะ | หลักฐาน |
|---|---|---|
| โหมดการทำงาน | Capital Protection — decision `WAIT` | `README.md`, `strategy/RUNBOOK.md` |
| Kill switch (paper bot) | ACTIVE ที่ drawdown 15.84% ของ paper bankroll **[ต้องยืนยัน]** ว่าตัวเลขยังเป็นปัจจุบัน | `docs/READINESS_CHECKLIST.md` (อัปเดตล่าสุด 2026-06-23) |
| เงินจริง | ถูกล็อก (`POLY_DRY_RUN=true`, futures mainnet ถูกปฏิเสธโดย engine) | `README.md` §Leveraged Market Scope |
| Readiness gate | Gate 0 กำลังเก็บข้อมูล, Gate 1–4 ยังไม่พร้อม | `docs/READINESS_CHECKLIST.md` §Current Status |
| CI | GitHub Actions: Go test, frontend lint/tsc/test/build, strategy pytest + ruff, build image | `.github/workflows/ci-cd.yml` |
| Deploy production | Manual เท่านั้น (`workflow_dispatch` + `deploy_production=true`) ยังไม่มีโดเมน/secret | `docs/READINESS_CHECKLIST.md` Gate 4 |
| Live URL | ไม่มี | `00-product-card.md` |
| Commit | 117 commits (2026-03-27 ถึง 2026-10-01) | `git log` |

## 3. ผู้ใช้หลัก

| ผู้ใช้ | บทบาท | หมายเหตุ |
|---|---|---|
| เจ้าของระบบ (operator) | admin คนเดียว: ดู dashboard, รัน monitor, ตัดสินใจเรื่อง gate | ผู้ใช้จริงคนเดียวที่มีหลักฐาน |
| ผู้สัมภาษณ์/ผู้ประเมิน portfolio | อ่านโค้ดและเอกสารเป็น Tier A flagship | `PRODUCT.md` |
| ผู้ใช้ภายนอก/ลูกค้า | ไม่มีหลักฐาน **[ต้องยืนยัน]** | roadmap ระบุ multi-user RBAC ยังไม่ทำ |

## 4. ตารางรายการเอกสาร

| รหัส | ไฟล์ | ชื่อ | ผู้อ่านหลัก |
|---|---|---|---|
| CARD-booktrading | `00-product-card.md` | Product Card | Product owner |
| BTR-DOC-00 | `00-overview.md` | ภาพรวมระบบและสารบัญเอกสาร | ทุกคน |
| BTR-DOC-01 | `01-prd.md` | Product Requirements (PRD) | Product owner |
| BTR-DOC-02 | `02-architecture.md` | System Architecture | Solution Architect, นักพัฒนา |
| BTR-DOC-03 | `03-nfr-security.md` | NFR และความปลอดภัย | Solution Architect, Security |
| BTR-DOC-04 | `04-runbook.md` | Runbook การติดตั้งและดูแลระบบ | Operator / DevOps |
| BTR-DOC-05 | `05-srs.md` | Software Requirements (SRS) | BA, นักพัฒนา |
| BTR-DOC-06 | `06-ux-flows.md` | User Flow และ Screen Inventory | UX/UI |
| BTR-DOC-07 | `07-test-uat.md` | Test Strategy และ UAT | QA |
| BTR-DOC-08 | `08-rtm.md` | Requirements Traceability Matrix | BA + QA |

## 5. วิธีอ่าน

1. เริ่มที่ `00-product-card.md` เพื่อดูคำตัดสิน `invest` และช่องว่างหลัก
2. อ่าน `01-prd.md` เพื่อเข้าใจว่าผลิตภัณฑ์ตั้งใจ *ไม่* เทรดจนกว่าจะมีหลักฐาน
3. นักพัฒนาอ่าน `02-architecture.md` → `05-srs.md` → `08-rtm.md`
4. ผู้ดูแลระบบอ่าน `04-runbook.md` คู่กับ `strategy/RUNBOOK.md` (decision tree ฉบับเต็ม)
5. ทุกตัวเลขผลการเทรดในชุดนี้เป็นของ **paper bankroll** ไม่ใช่เงินจริง

## การอนุมัติ

| บทบาท | สถานะ | วันที่ | ลงนาม |
|---|---|---|---|
| Product owner (Book Dev) | รอตรวจ | — | [ต้องยืนยัน] |

## แหล่งข้อมูล

- `README.md`, `PRODUCT.md`, `RUNBOOK.md`, `strategy/RUNBOOK.md`
- `docs/READINESS_CHECKLIST.md`, `docs/EVIDENCE_LOG.md`, `docs/UPGRADE-PLAN.md`
- `.github/workflows/ci-cd.yml`
- `DOCPACK/00-product-card.md`
