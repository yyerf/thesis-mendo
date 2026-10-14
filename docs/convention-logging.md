# Convention logging — October 15, 2026

Before hands-on use, stop the Flask app and hardware daemon. On the actual kiosk,
run these commands from the repository root with its Python environment active:

```sh
python tools/prepare_event_logs.py --event convention-2026-10-15
python tools/prepare_event_logs.py --event convention-2026-10-15 --apply
```

The first command previews counts. The second saves a verified, complete SQLite
backup, old runtime logs, and a manifest under `logs/archive/<UTC-time>_convention-2026-10-15/`.
It clears only consultation interactions, reviews, adjudications, and anonymous
operational counters. Inventory, users, orders, transactions, stock movements,
cash events, and receipts remain. Interaction IDs continue normally.
The manifest records before/after counts, backup hashes, Git revision, changed
file names, and source hashes identifying the local build. A `source/` snapshot
preserves local application code and the medicine dataset, including uncommitted
changes, for reproducing a reported issue.

Start the app again and open a fresh kiosk browser session. Keep preparation
checks separate from participant use: if you do test consultations afterward,
run preparation once more before opening the booth. Resetting this Windows
checkout does not reset a separate Raspberry Pi database.

During the convention, use a new consultation for each participant. The admin
Logs page groups consented steps by session, including symptom interpretation,
clarifications, severity, duration, recommendations, and decision traces.
Declined consent records only anonymous counters. For an issue, record the local
time, consultation/session ID when available, what was expected, what happened,
and the staff reproduction steps. For checkout problems include the order or
receipt ID, so it can be matched to retained payment and inventory evidence.

After the booth closes, stop the app and daemon and copy the entire `data/` and
`logs/` directories to a secure local backup. Export consultation JSON from
Admin Logs for review. Keep the original database because exports alone do not
include all payment, inventory, review, and receipt evidence. Archives contain
raw data and account records; they are ignored by Git and should stay private.
Do not replace a live database with an old backup during the convention:
inspect a copy to avoid rolling back sales or stock.
