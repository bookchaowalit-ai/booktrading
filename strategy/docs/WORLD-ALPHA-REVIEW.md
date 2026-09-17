# World snapshot → alpha review

สถานะ: อ่าน snapshot ใน local lake และสร้าง paper decision ได้ ยังไม่มี
official release feed, ตัวประมาณ fair value อัตโนมัติ หรือ scheduler
ผลทดสอบเป็น synthetic data ไม่ใช่ forward performance จริง

โมดูลอ่าน manifest ที่ commit แล้ว ตรวจ hash ของ raw และ Bronze และตรวจ
ว่า Bronze ตรงกับ raw ก่อนใช้ราคา ask ของ YES/NO ฝั่งที่ระบุ
ไม่มีการ fetch URL หรือส่ง order จาก CLI นี้

## วิธีใช้

จากโฟลเดอร์ strategy:

```bash
python scripts/world_alpha_review.py \
  --lake-root /absolute/path/to/local-lake \
  --manifest-key control/manifests/source=world_xyz/dataset=world_markets/schema_version=1/event_id=world-events-HASH.json \
  --thesis /absolute/path/to/thesis.json \
  --review /absolute/path/to/review.json \
  --open-risk 0 --open-positions 0
```

ระบุ exposure จริงของ paper portfolio อย่ากรอกศูนย์หากมี position ค้างอยู่
ค่าปกติใช้เวลาปัจจุบัน; `--as-of` ใช้สำหรับ replay และติดป้าย
`historical_replay=true` ในผลลัพธ์

thesis.json ใช้รูปแบบ `AlphaThesis.as_dict()` จาก alpha models
review.json มีสามส่วน:

- `risk_budget`: รูปแบบ `RiskBudget.as_dict()` ระบุวงเงิน paper ชัดเจน
- `cost_per_unit`: ค่า fee/slippage reserve ต่อหน่วย; ไม่มีค่าจะ WAIT
- `mapping`: ticker แบบตรงตัว, instrument_id ของ thesis, question,
  resolution_source, close_time, reviewed_at, thesis_sha256, evidence_objects

และมี binding ของ paper account:

- `account_scope`: alias ของบัญชีจำลอง เช่น `world-paper-usd`; ห้ามใช้ wallet
  address หรือ credential
- `quote_currency`: currency ของดีล เช่น `USD`; ระบบไม่ทำ FX อัตโนมัติ
- `starting_capital`: ทุนเริ่มต้นของบัญชีจำลอง (ถ้าระบุ ทุก review ใน account
  เดียวกันต้องใช้ค่าเดียวกัน)

`activity_mode` ของ durable journal ถูกบังคับเป็น `paper` เสมอ เพื่อไม่ให้
review นี้ถูกใช้เป็น testnet/live execution โดยบังเอิญ

`thesis_sha256` คำนวณจาก UTF-8 ของ
`json.dumps(thesis.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
การเปลี่ยน thesis หลัง review จะถูกปฏิเสธ

`evidence_objects` เป็น object ที่ใช้ evidence_id เป็น key แต่ละรายการมี
`key` (relative local lake object), `sha256`, `source_url`,
`published_at`, `received_at` ค่าเวลาที่มาทีหลังต้องเท่ากับ
observed_at ของ AlphaEvidence และต้องไม่เกิน reviewed_at
source_url ต้องตรงกับ evidence ด้วย

ดูตัวอย่าง input ที่สร้างและเรียก CLI ครบเส้นทางได้ใน
[test_world_alpha_snapshot.py](../tests/test_world_alpha_snapshot.py)

## ความหมายของผลลัพธ์และขอบเขต

stdout เป็น JSON ที่มี decision, observation, manifest reference และ journal
events สำหรับ consumer นำไปเก็บผ่าน pipeline ของตน
เพิ่ม `--journal-db /absolute/path/to/paper-lane.sqlite` เพื่อบันทึกถาวร
และตัด `--open-risk` / `--open-positions` ออก ระบบจะอ่าน exposure
และจอง risk ใน SQLite transaction เดียวกัน รองรับ retry หลัง restart
โดยคืน decision เดิม (`journal_retry=true`) ไม่ใช่สัญญาณเข้าใหม่

เมื่อใช้ `--journal-db` ทุก reservation จะถูกแยกตาม `account_scope` +
`quote_currency` + `activity_mode` และ `instrument` เดิมจะถูกกันซ้ำเฉพาะใน
บัญชีนั้น ไม่รบกวนบัญชี World/Fomo จำลองคนละใบ

## ปิดดีล paper และคืน risk

เมื่อมีผลลัพธ์จากแหล่งที่ review แล้ว ให้เขียนหลักฐานผลลัพธ์เป็นไฟล์ JSON
ใน local lake เช่น:

```json
{"ticker":"EXACT-TICKER","payout_per_unit":1}
```

`payout_per_unit` ของ binary market ต้องเป็น `0` หรือ `1` เท่านั้น จากนั้น
เรียก:

```bash
python scripts/world_alpha_settle.py \
  --journal-db /absolute/path/to/paper-lane.sqlite \
  --request-id <journal_request_id> \
  --lake-root /absolute/path/to/local-lake \
  --payout-per-unit 1 \
  --evidence-id official-settlement \
  --evidence-source world_xyz \
  --evidence-object-key landing/official-settlement.json \
  --evidence-sha256 <sha256-of-the-file> \
  --evidence-url https://official.example/settlement \
  --evidence-observed-at 2026-09-12T02:00:00Z \
  --evidence-summary "Official result reviewed by operator" \
  --ticker EXACT-TICKER \
  --settled-at 2026-09-12T02:00:00Z
```

คำสั่งจะตรวจขนาดไฟล์, SHA-256, ticker ถ้ามีในหลักฐาน, และ payout
ก่อนเขียน settlement transaction เดียวกับการคืน reservation ผลตอบแทนคำนวณ
จาก `(payout_per_unit - ask_price - cost_per_unit) * target_units`
จึงไม่ใช้ราคา exit ในอนาคตหรือเลข P&L ที่ผู้เรียกส่งมาเอง การเรียกซ้ำด้วย
หลักฐานและเวลาเดิมจะคืนผลเดิมพร้อม `journal_retry=true`; หลักฐานคนละชุด
จะถูกปฏิเสธ

หลัง settlement ผลลัพธ์จะมีสามส่วนที่เชื่อมกันด้วย request ID เดิม:

- `paper_trade`: closed trade ใน account/currency ของ review
- `portfolio.capital`: `starting_capital + realized_pnl - reserved_risk` หลังคืน
  risk แล้ว
- `finance_projection`: P&L แบบ non-cash ที่มี `cash_effect=false` และ
  `posting_status=separate_paper_lane`

projection นี้เป็น contract ส่งต่อให้ central finance/reconciliation เท่านั้น
ไม่ถูกเขียนเข้า `financial_transactions` อัตโนมัติ และ pending airdrop value
ก็ไม่ถูกนับเป็น cash

`reconcile(request_id)` ใช้ตรวจว่า reservation ถูกคืนแล้วหรือยังโดยไม่อ่าน
payload ดิบออกมา หรือเรียกจาก shell ได้ด้วย:

```bash
python scripts/world_alpha_reconcile.py \
  --journal-db /absolute/path/to/paper-lane.sqlite \
  --request-id <journal_request_id>
```

ปัจจุบันเป็น settlement แบบ manual review จากไฟล์ local
เท่านั้น ยังไม่มีการ fetch release URL อัตโนมัติหรือการส่ง order จริง

DB นี้เป็น operational control state สำหรับ decision ที่เกิดจากข้อมูล
lake เท่านั้น ไม่เก็บ raw source payload และไม่ได้แทน source lake
policy และโหมด historical/current ถูกตรึงตอนบันทึกครั้งแรก
การเปลี่ยน policy ต้องผ่าน migration ที่ตรวจ exposure แล้ว
ห้ามสร้าง DB ใหม่เพียงเพื่อเลี่ยง risk ที่ค้างอยู่

portfolio นี้ครอบคลุมเฉพาะ paper lane ใน DB เดียว ไม่รวม bot อื่น
ทุก TRADE_PAPER จอง worst-case risk จนกว่าจะมี settlement path ที่ตรวจสอบ
ได้ เมื่อ settlement proof ผ่านจึงปล่อย reservation และบันทึก realized P&L
ใน row เดิมแบบ idempotent พร้อม finance projection และ paper trade ที่ผูกกับ
account เดิม พร้อมกันการเข้า ticker เดิมซ้ำตราบใดที่ดีลเดิม
ยังไม่ถูก settle แม้คนละ thesis/คนละฝั่ง จึงยังไม่เปิด scheduler แบบต่อเนื่อง

checksum ใช้ตรวจ lineage ไม่ใช่การเข้ารหัส DB เก็บข้อมูลวิจัยภายใน
ควรวางใน private runtime directory ที่ไม่ถูก commit และสำรองก่อนย้าย
เฉพาะ normalized decisions ที่ประเมินสำเร็จถูกบันทึก; input ที่ผิดก่อน
evaluation จะคืน error โดยไม่มี journal row

checksum ยืนยันความสอดคล้องของไฟล์ ไม่ได้ยืนยันว่าข้อมูลเป็นประกาศทางการ
ผู้ review ต้องตรวจเนื้อหาและการใช้สิทธิ์ของ source ก่อนสร้าง mapping
รายการ evidence ต้องอ้างอิงข้อมูลที่ผ่าน landing/Bronze pipeline ของเจ้าของ
source แล้ว bridge ตรวจ bytes ของหลักฐานแต่ยังไม่ตรวจ Bronze contract ของ
official-release source เพราะยังไม่มี adapter นั้น

เมื่อ manifest/หลักฐานไม่ครบ hash ไม่ตรง กติกาเปลี่ยน หรือเวลาไม่ถูกต้อง
CLI จะคืน WAIT พร้อม error_class และ exit code 2 โดยไม่แสดง payload ดิบ
เมื่อ quote เก่า ขนาดไม่ทราบ หรือต้นทุนไม่ทราบ evaluator จะคืน WAIT พร้อม
reason codes การใช้ external feed และการเก็บผล prospective ยังต้องทำต่อ
