from unittest import TestCase
from web.blueprints.helpers.lazy_join import lazy_join


class LazyJoinTest(TestCase):
    def test_simple_join(self):
        @lazy_join
        def foo():
            yield "one"
            yield "two"
            yield "three"
        self.assertEqual(str(foo()), "onetwothree")

    def test_join_with_spaces(self):
        @lazy_join(" ")
        def foo():
            yield "one"
            yield "two"
            yield "three"

        self.assertEqual(str(foo()), "one two three")

    def test_elements_are_cast_to_string(self):
        @lazy_join
        def foo():
            yield "a"
            yield 3
            yield False
            yield None

        self.assertEqual(str(foo()), "a3False")
        self.assertEqual(list(foo()), ["a", "3", "False", ""])

    def test_glue_is_added_in_iterator(self):
        @lazy_join("\n")
        def foo():
            yield "one"
            yield "two"
            yield "three"

        self.assertEqual(list(foo()), ["one", "\n", "two", "\n", "three"])

    def test_nested_usage(self):
        @lazy_join(", ")
        def inner():
            yield "a"
            yield "b"

        @lazy_join("\n")
        def outer():
            yield "<span>"
            yield inner()
            yield "</span>"

        self.assertEqual(str(outer()), "<span>\na, b\n</span>")

    def test_exhaustion(self):
        @lazy_join
        def foo():
            yield "a"
            yield "b"

        combinations = [(str, str), (str, list), (list, str), (list, list)]
        for call1, call2 in combinations:
            with self.subTest(call1=call1, call2=call2):
                gen = foo()
                print(f"Calling {call1}, {call2} on gen=foo()")
                call1(gen)
                with self.assertRaises(RuntimeError):
                    call2(gen)
