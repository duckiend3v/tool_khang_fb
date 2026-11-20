"""Regression checks for 2FA submission and sequential profile cleanup."""
import ast
import re
from pathlib import Path
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.value = 100.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def load_methods(path, class_name, names, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    methods = [n for n in cls.body if getattr(n, "name", "") in names]
    exec(compile(ast.Module(body=methods, type_ignores=[]), path, "exec"), namespace)
    return namespace


class LoginCloseFlowTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.driver = Mock(current_url="https://www.facebook.com/")
        self.closed_at = []
        self.driver.quit.side_effect = lambda: self.closed_at.append(self.clock.value)
        self.bot = SimpleNamespace(twofa_continue_clicked_at=None, twofa_result=None)
        self.worker = SimpleNamespace(
            acc_data={"id": "test", "password": "test-password"},
            platform="facebook", index=0, keep_browser_open=False,
            signals=SimpleNamespace(started=Mock(), status=Mock(), error=Mock(), finished=Mock()),
            success=False, driver=None, is_running=True, login_bot=None, _browsers=[],
            is_facebook_session_alive=Mock(return_value=False),
        )
        namespace = {
            "time": self.clock,
            "ProfileManager": lambda: SimpleNamespace(get_profile_path=lambda *args: "test-profile"),
            "ChromeLauncher": SimpleNamespace(launch=lambda *args, **kwargs: self.driver),
        }
        self.methods = load_methods(
            "core/worker.py", "BatchLoginWorker", {"run", "stop", "_wait_after_twofa_continue"}, namespace
        )
        self.worker._wait_after_twofa_continue = MethodType(
            self.methods["_wait_after_twofa_continue"], self.worker
        )

    def configure_login(self, success, elapsed=0, clicked=True):
        def login(driver):
            self.worker.login_bot = self.bot
            if clicked:
                self.bot.twofa_continue_clicked_at = self.clock.value
            self.clock.sleep(elapsed)
            self.driver.current_url = "https://web.facebook.com/checkpoint/final-result"
            return success
        self.worker.apply_facebook_support_data = login

    def test_success_waits_twelve_seconds_then_saves_final_url_before_quit(self):
        self.configure_login(True)
        self.methods["run"](self.worker)
        self.assertEqual(self.closed_at, [112.0])
        self.assertEqual(self.worker.acc_data["login_resume_url"], self.driver.current_url)
        self.worker.signals.finished.emit.assert_called_once_with(0)

    def test_rejected_twofa_still_waits_after_continue(self):
        self.configure_login(False, elapsed=1)
        self.bot.twofa_result = "rejected"
        self.methods["run"](self.worker)
        self.assertEqual(self.closed_at, [112.0])
        self.assertFalse(self.worker.success)
        self.assertEqual(self.worker.acc_data["login_resume_url"], self.driver.current_url)

    def test_response_already_took_twelve_seconds_has_no_extra_delay(self):
        self.configure_login(True, elapsed=12)
        self.methods["run"](self.worker)
        self.assertEqual(self.closed_at, [112.0])

    def test_failed_submit_is_not_reported_as_success(self):
        self.configure_login(False, clicked=False)
        self.bot.twofa_result = "submit_failed"
        self.methods["run"](self.worker)
        self.assertFalse(self.worker.success)
        messages = [c.args[1] for c in self.worker.signals.status.emit.call_args_list]
        self.assertTrue(any("Không bấm được Continue" in msg for msg in messages))

    def test_stop_interrupts_wait_and_saves_url_before_closing(self):
        self.configure_login(False)
        original_sleep = self.clock.sleep

        def stop_during_sleep(seconds):
            original_sleep(seconds)
            self.methods["stop"](self.worker)
        self.clock.sleep = stop_during_sleep
        self.methods["run"](self.worker)
        self.assertFalse(self.worker.is_running)
        self.assertLess(self.closed_at[0], 105.0)
        self.assertEqual(self.worker.acc_data["login_resume_url"], self.driver.current_url)


class ContinueSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.driver = Mock()
        self.button = Mock()
        self.disabled = True
        self.button.get_attribute.side_effect = lambda name: (
            "true" if self.disabled else "false"
        ) if name == "aria-disabled" else None
        self.driver.find_elements.return_value = [self.button]
        self.bot = SimpleNamespace(driver=self.driver, safe_click=Mock(return_value=True))
        self.methods = load_methods(
            "facebook/fb_tasks.py", "FacebookBot", {"_submit_twofa_continue"},
            {"time": self.clock, "By": SimpleNamespace(XPATH="xpath")},
        )

    def test_disabled_continue_is_never_clicked(self):
        result = self.methods["_submit_twofa_continue"](self.bot, timeout=1)
        self.assertFalse(result)
        self.bot.safe_click.assert_not_called()
        self.assertFalse(hasattr(self.bot, "twofa_continue_clicked_at"))

    def test_waits_for_enabled_continue_and_records_click_once(self):
        original_sleep = self.clock.sleep

        def enable_on_next_poll(seconds):
            original_sleep(seconds)
            self.disabled = False
        self.clock.sleep = enable_on_next_poll
        result = self.methods["_submit_twofa_continue"](self.bot, timeout=1)
        self.assertTrue(result)
        self.bot.safe_click.assert_called_once_with(self.button)
        self.assertEqual(self.bot.twofa_continue_clicked_at, 100.2)

    def test_click_failure_does_not_record_a_submission(self):
        self.disabled = False
        self.bot.safe_click.return_value = False
        result = self.methods["_submit_twofa_continue"](self.bot, timeout=1)
        self.assertFalse(result)
        self.assertFalse(hasattr(self.bot, "twofa_continue_clicked_at"))


class TwofaOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.field = Mock()
        self.field.get_attribute.return_value = "123456"
        self.field.get_dom_property.return_value = "123456"
        self.driver = Mock(current_url="https://web.facebook.com/two_step_verification/two_factor/")
        self.driver.find_elements.return_value = [self.field]
        self.bot = SimpleNamespace(
            driver=self.driver,
            extract_2fa_code_from_2fa_live=Mock(return_value="123456"),
            _submit_twofa_continue=Mock(return_value=True),
        )
        methods = load_methods(
            "facebook/fb_tasks.py", "FacebookBot", {"apply_2fa_code"},
            {
                "time": self.clock, "re": re, "By": SimpleNamespace(XPATH="xpath"),
                "WebDriverWait": lambda driver, *args, **kwargs: SimpleNamespace(until=lambda condition: condition(driver)),
            },
        )
        self.apply = MethodType(methods["apply_2fa_code"], self.bot)

    def test_filling_code_without_continue_is_not_success(self):
        self.bot._submit_twofa_continue.return_value = False
        self.assertFalse(self.apply("test-secret"))
        self.assertEqual(self.bot.twofa_result, "submit_failed")
        self.assertIsNone(self.bot.twofa_continue_clicked_at)
        self.field.send_keys.assert_called_once_with("123456")

    def test_wrong_input_value_does_not_click_continue(self):
        self.field.get_attribute.return_value = "123"
        self.field.get_dom_property.return_value = "123"
        self.assertFalse(self.apply("test-secret"))
        self.assertEqual(self.bot.twofa_result, "fill_failed")
        self.bot._submit_twofa_continue.assert_not_called()

    def test_next_screen_with_same_url_is_accepted_after_submit(self):
        self.driver.find_elements.side_effect = lambda by, xpath: (
            [self.field] if self.clock.value < 100.25 and xpath.startswith("//input") else []
        )
        self.driver.execute_script.return_value = True
        self.assertTrue(self.apply("test-secret"))
        self.assertEqual(self.bot.twofa_result, "next_page")
        self.bot._submit_twofa_continue.assert_called_once()


if __name__ == "__main__":
    unittest.main()
