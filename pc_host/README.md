# Trinity PC host — Primer #1 control-plane bring-up

Install from the repository root on Windows:

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e pc_host
```

List ports:

```bat
python -m trinity_host.cli ports
```

Run the complete Primer #1 control-plane gate:

```bat
python -m trinity_host.cli --port COM7 p1-bringup
```

The command performs, in order:

```text
PC -> SN32 PING
SN32 -> P1 GET_INFO
SN32 -> P1 GET_STATUS
SN32 -> P1 RUN_SELF_TEST
SN32 -> P1 GET_TXN_RESULT (polled until terminal)
SN32 -> P1 RETIRE_TXN_RESULT
SN32 -> P1 GET_STATUS (final confirmation)
```

This gate does not issue session, encryption, Primer #2 or Tiny commands.
