"""Exercise the login methods without real accounts or browser dependencies."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


def load_login_methods():
    source = ast.parse((ROOT / 'facebook/fb_tasks.py').read_text(encoding='utf-8'))
    bot = next(node for node in source.body if isinstance(node, ast.ClassDef))
    names = {'login_account_with_credentials', 'login_with_credentials'}
    methods = [node for node in bot.body if getattr(node, 'name', '') in names]
    clock = [0.0]

    def now():
        clock[0] += 0.2
        return clock[0]

    namespace = {
        'time': SimpleNamespace(sleep=Mock(), time=now),
        'By': SimpleNamespace(ID='id', NAME='name', XPATH='xpath', CSS_SELECTOR='css'),
        'Keys': SimpleNamespace(ENTER='enter'),
    }
    namespace['WebDriverWait'] = lambda driver, timeout, **kwargs: SimpleNamespace(
        until=lambda condition: condition(driver)
    )
    exec(compile(ast.Module(body=methods, type_ignores=[]), '<login-methods>', 'exec'), namespace)
    return namespace


class UidPasswordLoginTests(unittest.TestCase):
    def setUp(self):
        self.methods = load_login_methods()
        self.bot = SimpleNamespace(
            driver=SimpleNamespace(current_url='https://www.facebook.com/'),
            login_with_credentials=Mock(return_value=True),
            wait_for_2fa_and_fill=Mock(return_value=True),
            save_credentials_to_browser=Mock(),
            enable_chrome_autofill=Mock(),
        )
        self.account = {
            'id': 'test-uid', 'password': 'test-password',
            'cookie': 'unused-cookie', 'token': 'unused-token',
            'email': 'unused-email', 'email_password': 'unused-mail-password',
            '2fa_code': 'test-2fa',
        }

    def login(self):
        return self.methods['login_account_with_credentials'](self.bot, self.account)

    def test_only_assigned_uid_and_password_are_submitted(self):
        self.assertTrue(self.login())
        self.bot.login_with_credentials.assert_called_once_with('test-uid', 'test-password')
        self.bot.wait_for_2fa_and_fill.assert_not_called()

    def test_missing_password_does_not_fall_back_to_cookie_token_or_mail(self):
        self.account['password'] = ''
        self.assertFalse(self.login())
        self.bot.login_with_credentials.assert_not_called()

    def test_failed_login_does_not_save_credentials(self):
        self.bot.login_with_credentials.return_value = False
        self.assertFalse(self.login())
        self.bot.save_credentials_to_browser.assert_not_called()

    def test_twofa_is_handled_after_credential_submission(self):
        self.bot.driver.current_url = 'https://web.facebook.com/two_step_verification/two_factor/'
        self.assertTrue(self.login())
        self.bot.wait_for_2fa_and_fill.assert_called_once_with('test-2fa', timeout=45)

    def test_failed_twofa_does_not_save_credentials(self):
        self.bot.driver.current_url = 'https://web.facebook.com/two_step_verification/two_factor/'
        self.bot.wait_for_2fa_and_fill.return_value = False
        self.assertFalse(self.login())
        self.bot.save_credentials_to_browser.assert_not_called()

    def test_visible_form_is_filled_without_another_navigation(self):
        username, password, button = Mock(), Mock(), Mock()
        driver = Mock(current_url='https://www.facebook.com/')

        def find_elements(by, selector):
            if selector in ('email', "input[type='email'], input[autocomplete='username']"):
                return [username]
            if selector in ('pass', "input[type='password'], input[autocomplete='current-password']"):
                return [password]
            if selector.startswith('button'):
                return [button]
            return []

        driver.find_elements.side_effect = find_elements
        bot = SimpleNamespace(
            driver=driver,
            _login_form_present=Mock(side_effect=[True, False]),
            safe_find_element=Mock(side_effect=[username, password, button]),
            safe_click=Mock(return_value=True),
        )
        self.assertTrue(self.methods['login_with_credentials'](bot, 'test-uid', 'test-password'))
        driver.get.assert_not_called()
        username.send_keys.assert_called_once_with('test-uid')
        password.send_keys.assert_called_once_with('test-password')
        bot.safe_click.assert_called_once_with(button)

    def test_staying_on_login_form_is_not_success(self):
        username, password, button = Mock(), Mock(), Mock()
        driver = Mock(current_url='https://www.facebook.com/')
        driver.find_elements.return_value = [username]
        bot = SimpleNamespace(
            driver=driver, _login_form_present=Mock(return_value=True),
            safe_find_element=Mock(side_effect=[username, password, button]),
            safe_click=Mock(return_value=True),
        )
        self.assertFalse(self.methods['login_with_credentials'](bot, 'test-uid', 'test-password'))


if __name__ == '__main__':
    unittest.main()
