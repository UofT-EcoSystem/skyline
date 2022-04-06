This page describes the database schema of the run time report that is generated by Skyline's `time` subcommand. Recall
that Skyline's reports (memory and run time) are [SQLite database files](https://www.sqlite.org/).

## Overview

Skyline's run time report contains a breakdown of the run times of each operation that runs in one training iteration. Skyline only tracks the
operations that execute as a part of either the forward and backward pass.

For each tracked operation, Skyline also includes the stack trace leading to that operation. Skyline only includes the stack frames associated with files inside your project (i.e. files under your project's root directory).

## Tables

### `run_time_entries`

```sql title="Schema"
CREATE TABLE run_time_entries (
  id INTEGER PRIMARY KEY,
  operation_name TEXT NOT NULL,
  forward_ms REAL NOT NULL,
  backward_ms REAL
);
```

This table holds the measured run time(s) of each tracked operation. Each entry in this table represents one operation *instance* (i.e. one invocation of an operation). The columns in this table are self-explanatory.

**NOTE:** Skyline reports run times in milliseconds.

**Backward Pass.**
Note that not every operation is necessarily involved in the backward pass. When an operation is not in the backward pass, `backward_ms` will be `NULL`.


### `stack_frames`

```sql title="Schema"
CREATE TABLE stack_frames (
  ordering INTEGER NOT NULL,
  file_path TEXT NOT NULL,
  line_number INTEGER NOT NULL,
  entry_id INTEGER NOT NULL,
  PRIMARY KEY (entry_id, ordering)
);
```

This table holds the stack frames associated with each tracked operation. The `entry_id` column is a foreign key that references the `id` column in `run_time_entries`.

**NOTE** Skyline does not add an explicit foreign key constraint to the `entry_id` column.

**Ordering.**
There may be multiple stack frames associated with any given tracked operation (i.e. any given `entry_id`). The `ordering` column is used to keep track of the ordering among stack frames that share the same `entry_id`. When sorted in ascending order by the `ordering` column, the stack frames will be ordered from most-specific (i.e. *closest* to the operation's call site) to least-specific (i.e. *farthest* from the operation's call site).