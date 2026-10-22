# An island: a normal ultra app, mounted inside a page.
from lpython import i32, Const
from ultra import el, end, num, text, cls
from ui import btn, card_open, card_header, card_content_open

INC: Const[i32] = 1
DEC: Const[i32] = 2
RESET: Const[i32] = 3

count: i32 = 0


def update(msg: i32, arg: i32) -> None:
    global count
    if msg == INC:
        count += arg
    elif msg == DEC:
        count -= arg
    elif msg == RESET:
        count = 0


def view() -> None:
    card_open()
    card_header("An island", "This counter is its own ultra app, embedded in the page.")
    card_content_open()
    el("div")
    cls("counter-row")
    btn("−", "outline", DEC, 1)
    el("span")
    cls("counter-value")
    num(count)
    end()
    btn("+", "", INC, 1)
    btn("Reset", "ghost", RESET, 0)
    end()
    end()
    end()
