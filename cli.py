#!/usr/bin/env python
# _*_ encoding: utf-8 _*_


import getpass


def prompt(name, default=None):
    """
    提示用户输入文本

    :param name: 提示文字
    :param default: 默认值
    """

    prompt = name + (default and ' [%s]' % default or '')
    prompt += name.endswith('?') and ' ' or ': '
    while True:
        rv = input(prompt)
        if rv:
            return rv
        if default is not None:
            return default


def prompt_pass(name, default=None):
    """
    提示用户输入密码

    :param name: 提示文字
    :param default: 默认值
    """

    prompt = name + (default and ' [%s]' % default or '')
    prompt += name.endswith('?') and ' ' or ': '
    while True:
        rv = getpass.getpass(prompt)
        if rv:
            return rv
        if default is not None:
            return default


def prompt_bool(name, default=False, yes_choices=None, no_choices=None):
    """
    提示用户输入布尔值（是或否）

    :param name: 提示文字
    :param default: 默认值
    :param yes_choices: 是的默认值 'y', 'yes', '1', 'on', 'true', 't'
    :param no_choices: 否的默认值 'n', 'no', '0', 'off', 'false', 'f'
    """

    yes_choices = yes_choices or ('y', 'yes', '1', 'on', 'true', 't')
    no_choices = no_choices or ('n', 'no', '0', 'off', 'false', 'f')

    while True:
        rv = prompt(name, yes_choices[0] if default else no_choices[0])
        if not rv:
            return default
        if rv.lower() in yes_choices:
            return True
        elif rv.lower() in no_choices:
            return False


def prompt_choices(name, choices, default=None, no_choice=('none',)):
    """
    提示用户输入选择项

    :param name: 提示文字
    :param choices: 可获取的选择项，可以是单个字符串或者(key, value)的列表
    :param default: 默认值
    :param no_choice: 可接受"空选择"的字符串列表
    """

    _choices = []
    options = []

    for choice in choices:
        if isinstance(choice, str):
            options.append(choice)
        else:
            options.append("%s [%s]" % (choice[1], choice[0]))
            choice = choice[0]
        _choices.append(choice)

    while True:
        rv = prompt(name + ' - (%s)' % ', '.join(options), default).lower()
        if rv in no_choice:
            return None
        if rv in _choices or rv == default:
            return rv
