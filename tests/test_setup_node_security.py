"""Regression tests for security-critical patterns in
dropsend_setup_node.py.

These run static AST analysis against the source file rather than
invoking setup() at runtime. Reasons:
  • setup() pulls in aiohttp, requests, dropbox, the Dropbox API,
    and several global modules. A behavioral test would be heavy.
  • The patterns we're guarding against are syntactic — "is there
    a send_sync call without a sid argument" is exactly the kind
    of regression an AST walk catches deterministically.

Catches:
  • The original WebSocket-broadcast vulnerability (send_sync with
    sid=None broadcasts to every connected client). Any future
    change that drops the `if sid:` guard or hardcodes None as the
    third argument fails this test loudly at CI time.

Run with:
  python -m unittest tests.test_setup_node_security
or:
  python tests/test_setup_node_security.py
"""

import ast
import os
import sys
import unittest


_SETUP_NODE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dropsend_setup_node.py",
)

# WebSocket events that carry credential data or trigger credential-
# adjacent UI changes. Any send_sync of one of these MUST NOT be a
# broadcast (sid=None).
CREDENTIAL_EVENTS = frozenset({
    "dropsend_credentials_ready",
    "dropsend_credentials_needed",
    "dropbox_reconnect_complete",
})


def _iter_send_sync_calls(tree):
    """Yield every call to a `*.send_sync(...)` attribute in the tree."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "send_sync":
            yield node


def _first_arg_is_credential_event(call):
    """If the first positional arg is a string literal naming a
    credential-class event, return that string; otherwise None."""
    if not call.args:
        return None
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        if arg.value in CREDENTIAL_EVENTS:
            return arg.value
    return None


class TestNoBroadcastForCredentialEvents(unittest.TestCase):
    """The dangerous pattern is `PromptServer.instance.send_sync(EVENT,
    DATA)` (no third arg) or `send_sync(EVENT, DATA, None)`. Both
    cause aiohttp's send_json to iterate every connected websocket
    and deliver to all of them — i.e. a credential broadcast.

    Every credential-class send_sync in the setup node must have a
    third argument, and that third argument must not be a `None`
    literal."""

    @classmethod
    def setUpClass(cls):
        with open(_SETUP_NODE_PATH, "r", encoding="utf-8") as f:
            cls.tree = ast.parse(f.read(), filename=_SETUP_NODE_PATH)

    def test_every_credential_send_sync_supplies_a_sid(self):
        offenders = []
        for call in _iter_send_sync_calls(self.tree):
            event = _first_arg_is_credential_event(call)
            if event is None:
                continue
            # Inspect the third positional or `sid=` keyword argument.
            sid_arg = None
            if len(call.args) >= 3:
                sid_arg = call.args[2]
            else:
                for kw in call.keywords:
                    if kw.arg == "sid":
                        sid_arg = kw.value
                        break
            if sid_arg is None:
                offenders.append(
                    f"send_sync({event!r}, ...) at line {call.lineno} "
                    "supplies no sid argument; this would broadcast to "
                    "every connected WebSocket client."
                )
                continue
            if isinstance(sid_arg, ast.Constant) and sid_arg.value is None:
                offenders.append(
                    f"send_sync({event!r}, ..., None) at line {call.lineno} "
                    "passes None as sid; this would broadcast to every "
                    "connected WebSocket client."
                )
        if offenders:
            self.fail(
                "Credential events must never be broadcast. Offenders:\n  "
                + "\n  ".join(offenders)
            )

    def test_every_credential_send_sync_is_inside_a_truthy_sid_check(self):
        """Static-analysis defense in depth: walk every credential
        send_sync and confirm it sits inside an `if sid:` (or `if X:`)
        block. Catches the case where someone supplies a truthy-looking
        variable that's actually `None` at runtime — the surrounding
        guard is what proves the variable is non-empty."""
        offenders = []
        # Build parent links so we can walk upward from each call.
        parent_of = {}
        for parent in ast.walk(self.tree):
            for child in ast.iter_child_nodes(parent):
                parent_of[id(child)] = parent

        def is_inside_truthy_check(node):
            cur = parent_of.get(id(node))
            while cur is not None:
                if isinstance(cur, ast.If):
                    test = cur.test
                    # Accept `if sid:` and `if some_var:` (Name node)
                    # and `if sid is not None:` style.
                    if isinstance(test, ast.Name):
                        return True
                    if (
                        isinstance(test, ast.Compare)
                        and len(test.ops) == 1
                        and isinstance(test.ops[0], (ast.IsNot, ast.NotEq))
                        and isinstance(test.comparators[0], ast.Constant)
                        and test.comparators[0].value is None
                    ):
                        return True
                    if (
                        isinstance(test, ast.UnaryOp)
                        and isinstance(test.op, ast.Not)
                    ):
                        # `if not sid: ... else: send_sync(...)` is
                        # also an acceptable guard.
                        return True
                cur = parent_of.get(id(cur))
            return False

        for call in _iter_send_sync_calls(self.tree):
            event = _first_arg_is_credential_event(call)
            if event is None:
                continue
            if not is_inside_truthy_check(call):
                offenders.append(
                    f"send_sync({event!r}, ...) at line {call.lineno} "
                    "is not inside an `if sid:` (or equivalent) guard. "
                    "Without the guard, a falsy/missing client_id "
                    "would silently broadcast credentials."
                )
        if offenders:
            self.fail(
                "Credential events must be inside a truthy-sid check. "
                "Offenders:\n  " + "\n  ".join(offenders)
            )


class TestSetupNodeHasNoCredentialInputs(unittest.TestCase):
    """The Setup Node's INPUT_TYPES must not declare app_key,
    app_secret, or auth_code as workflow inputs. The whole point of
    the modal architecture is that these never enter the prompt JSON;
    if they reappear in INPUT_TYPES, every leak vector we closed
    (workflow JSON, PNG metadata, /history, etc.) silently reopens."""

    FORBIDDEN_INPUT_NAMES = frozenset({"app_key", "app_secret", "auth_code"})

    @classmethod
    def setUpClass(cls):
        with open(_SETUP_NODE_PATH, "r", encoding="utf-8") as f:
            cls.source = f.read()
            cls.tree = ast.parse(cls.source, filename=_SETUP_NODE_PATH)

    def test_input_types_does_not_declare_credential_fields(self):
        # Find INPUT_TYPES in DropSendSetupNode. It returns a dict
        # literal of dicts; we check the keys at the inner level.
        offenders = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "INPUT_TYPES":
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Dict):
                    continue
                for key in sub.keys:
                    if (
                        isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and key.value in self.FORBIDDEN_INPUT_NAMES
                    ):
                        offenders.append(
                            f"{key.value!r} appears as a key in an INPUT_TYPES "
                            f"dict at line {key.lineno}. Setup-Node credentials "
                            "must NOT be workflow inputs — they go through the "
                            "modal + stash route, never the prompt body."
                        )
        if offenders:
            self.fail(
                "Forbidden credential fields declared as workflow inputs:\n  "
                + "\n  ".join(offenders)
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
