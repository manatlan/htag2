from htag.core import GTag, Tag, prevent, stop

def test_gtag_init():
    t = GTag("div", "hello")
    assert t.tag == "div"
    assert "hello" in t.childs
    assert t.id is not None
    assert t._GTag__dirty is True

def test_gtag_fallback_tag():
    # If first arg is a string and no tag defined, it becomes the tag
    t = GTag("my-custom-tag", "hello")
    assert t.tag == "my-custom-tag"
    assert "hello" in t.childs
    
    # Test line 48: div fallback if no args at all
    t2 = GTag()
    assert t2.tag == "div"

def test_gtag_add_remove():
    t = GTag("div")
    child = GTag("span")
    t._GTag__dirty = False
    t.add(child)
    assert child in t.childs
    assert child.parent == t
    assert t._GTag__dirty is True
    
    t._GTag__dirty = False
    t.remove(child)
    assert child not in t.childs
    assert child.parent is None
    assert t._GTag__dirty is True

def test_gtag_clear():
    t = GTag("div", "one", "two")
    t._GTag__dirty = False
    t.clear()
    assert len(t.childs) == 0
    assert t._GTag__dirty is True

def test_gtag_attr_magic():
    t = GTag("div", _class="foo", _data_id="123")
    assert t._class == "foo"
    assert t._GTag__attrs["class"] == "foo"
    assert t._GTag__attrs["data_id"] == "123"
    assert t.id is not None
    
    t._class = "bar"
    assert t._GTag__attrs["class"] == "bar"
    assert t._GTag__dirty is True
    
    # Test line 103: regular python attribute
    t.some_var = 42
    assert t.some_var == 42
    
    # Test line 96: event setter
    def other_h(e): pass
    t._onmouseover = other_h
    assert "mouseover" in t._GTag__events

def test_gtag_render_attrs():
    t = GTag("div", _class="foo", _data_id="123")
    rendered = t._render_attrs()
    assert 'class="foo"' in rendered
    assert 'data-id="123"' in rendered
    assert f'id="{t.id}"' in rendered

def test_gtag_events():
    def my_handler(e): pass
    t = GTag("button", _onclick=my_handler)
    assert "click" in t._GTag__events
    assert t._GTag__events["click"] == my_handler

def test_tag_creator():
    MyDiv = Tag.Div
    assert MyDiv.tag == "div"
    t = MyDiv("content")
    assert isinstance(t, GTag)
    assert t.tag == "div"
    assert "Div" in Tag._registry

def test_void_elements():
    # Test input (previously a special class)
    i = Tag.Input(_value="test")
    assert i.tag == "input"
    assert str(i).startswith("<input")
    assert "/>" in str(i)
    
    # Test other void elements
    assert "/>" in str(Tag.Img(_src="foo.png"))
    assert str(Tag.Br()).startswith("<br")
    assert "/>" in str(Tag.Br())

def test_decorators():
    @prevent
    def handle_p(e): pass
    @stop
    def handle_s(e): pass
    assert handle_p._htag_prevent is True
    assert handle_s._htag_stop is True

def test_gtag_str():
    t = GTag("div", "content")
    t.id = "fixme"
    assert str(t) == '<div id="fixme">content</div>'
    
    # Test line 159: fallback when tag is None
    t.tag = None
    assert str(t) == "content"

def test_gtag_list_addition():
    # Test lines 111-113 and 116-118
    t = GTag("div")
    l = [1, 2]
    res = t + l
    assert res == [t, 1, 2]
    
    res2 = l + t
    assert res2 == [1, 2, t]
    
    # Non list
    res3 = t + 3
    assert res3 == [t, 3]
    
    res4 = 4 + t
    assert res4 == [4, t]

def test_add_class():
    # Test lines 140-146
    t = GTag("div")
    t.add_class("foo")
    assert t._class == "foo"
    t.add_class("bar")
    assert t._class == "foo bar"
    t.add_class("foo") # already there
    assert t._class == "foo bar"

def test_gtag_iadd():
    t = GTag("div")
    t += "hello"
    assert "hello" in t.childs

def test_gtag_add_list():
    t = GTag("div")
    t.add(["a", "b"])
    assert "a" in t.childs
    assert "b" in t.childs

def test_gtag_call_js():
    t = GTag("div")
    t.call_js("alert(1)")
    assert "alert(1)" in t._GTag__js_calls

def test_gtag_remove_self():
    parent = GTag("div")
    child = GTag("span")
    parent.add(child)
    child.remove_self()
    assert child not in parent.childs
    assert child.parent is None

def test_gtag_le():
    t = GTag("div")
    t <= "hello"
    assert "hello" in t.childs
    
    child = GTag("span")
    t <= child
    assert child in t.childs
    assert child.parent == t

def test_gtag_root():
    class MyApp(Tag.App):
        pass

    app = MyApp()
    child1 = Tag.Div()
    child2 = Tag.Span()
    
    app += child1
    child1 += child2

    assert app.root is app
    assert child1.root is app
    assert child2.root is app

    # Not attached to an App
    unattached = Tag.Div()
    unattached_child = Tag.Span()
    unattached += unattached_child
    assert unattached.root is None
    assert unattached_child.root is None
