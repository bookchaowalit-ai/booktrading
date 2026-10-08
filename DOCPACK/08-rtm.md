---
title: BookFinance — Requirements Traceability Matrix
doc_id: BTR-DOC-08
doc_type: rtm
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: BA + QA (Book Dev)
related: 01-prd.md, 05-srs.md, 06-ux-flows.md, 07-test-uat.md
---

# BookFinance — Requirements Traceability Matrix

## 1. ตาราง FR ↔ US ↔ หน้าจอ ↔ TC ↔ หลักฐาน

| FR | ฟีเจอร์ (PRD) | US | หน้าจอ | TC | สถานะหลักฐาน |
|---|---|---|---|---|---|
| FR-01 | F-01 | US-01 | SC-01 | TC-01 | อัตโนมัติ (frontend contract); live contract รันเอง |
| FR-02 | F-03 | US-02 | SC-02 | TC-16 | UAT ด้วยมือเท่านั้น |
| FR-03 | F-05 | US-03 | SC-03, SC-08 | TC-16 | UAT ด้วยมือเท่านั้น |
| FR-04 | F-06 | US-04 | SC-04 | TC-13 | อัตโนมัติ (component test) |
| FR-05 | F-06 | US-05 | SC-05 | TC-16 | UAT ด้วยมือเท่านั้น |
| FR-06 | F-02 | US-06, US-07 | SC-01 | TC-02, TC-03 | อัตโนมัติ |
| FR-07 | F-02 | US-06 | SC-01 | TC-04 | อัตโนมัติ |
| FR-08 | F-07 | — | SC-07 | TC-07 | อัตโนมัติ |
| FR-09 | F-08 | US-08 | SC-07 | TC-05 | อัตโนมัติ |
| FR-10 | F-09 | US-09 | SC-08 | TC-06 | อัตโนมัติ |
| FR-11 | F-04 | US-10 | SC-11 | TC-08, TC-09, TC-10 | อัตโนมัติ |
| FR-12 | F-04 | US-10 | ทุกหน้าที่เรียก strategy | TC-11 | อัตโนมัติ |
| FR-13 | F-10 | US-01 | SC-07 | TC-15 | UAT ด้วยมือเท่านั้น |
| FR-14 | F-03 | US-11 | CLI | TC-12 | อัตโนมัติ |
| FR-15 | — | — | ทุกหน้า | TC-17 | UAT ด้วยมือเท่านั้น |
| FR-16 | F-11 | — | SC-09 | TC-14 | อัตโนมัติ (สิทธิ์เท่านั้น) |
| FR-17 | F-12 | — | SC-07 | TC-07 | อัตโนมัติบางส่วน (reconcile) |
| FR-18 | F-13 | US-06 | SC-09 | TC-18 | ไม่มีหลักฐาน |

## 2. ช่องว่างที่ยังไม่ครอบคลุม

| ID | ช่องว่าง | ผลกระทบ | ข้อเสนอ |
|---|---|---|---|
| GAP-01 | FR-02, FR-03, FR-05 (Core 5 สามหน้า) ไม่มี test เฉพาะ | หน้าที่เป็น trust surface อาจ regress (เคยมีบั๊ก rules-of-hooks ในหน้า Evidence ตาม `PRODUCT.md`) | เพิ่ม Vitest render test หรือ Playwright smoke ต่อหน้า |
| GAP-02 | FR-13 ไม่มี test ว่า advanced ถูกซ่อน | หน้าเทรดอาจโผล่ใน default UI | test ของ `Sidebar.tsx` ตาม env flag |
| GAP-03 | Playwright e2e ไม่ได้อยู่ใน CI | flow จริงไม่ถูกตรวจ | เพิ่ม job e2e แบบ headless |
| GAP-04 | FR-18 ไม่มีหลักฐานการแจ้งเตือนจริง | operator ไม่รู้ตัวเมื่อ kill switch ทำงาน | ทดสอบ webhook ใน staging และบันทึกใน evidence log |
| GAP-05 | NFR-05/06 (latency, uptime) ไม่มีการวัด | ตั้ง SLO ไม่ได้ | วัดหลังมี production (Gate 4) |
| GAP-06 | ไม่มีบันทึก UAT ลงนาม | ไม่มีหลักฐานการยอมรับ | operator ทำ UAT ตาม `07-test-uat.md` แล้วบันทึกผล |

## การอนุมัติ

| บทบาท | สถานะ | วันที่ | ลงนาม |
|---|---|---|---|
| BA (Book Dev) | รอตรวจ | — | [ต้องยืนยัน] |
| QA (Book Dev) | รอตรวจ | — | [ต้องยืนยัน] |

## แหล่งข้อมูล

- `DOCPACK/01-prd.md`, `DOCPACK/05-srs.md`, `DOCPACK/06-ux-flows.md`, `DOCPACK/07-test-uat.md`
- `PRODUCT.md` (บั๊ก rules-of-hooks ในหน้า Evidence)
- `.github/workflows/ci-cd.yml`
