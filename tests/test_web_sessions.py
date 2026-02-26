import pytest
from starlette.testclient import TestClient
from htag.server import WebServer
from htag import Tag

class MyApp(Tag.App):
    def __init__(self):
        super().__init__()
        self.count = 0
    def inc(self, e):
        self.count += 1

def test_multi_session_logic():
    """Verify that passing a class creates unique instances for different sids."""
    server = WebServer(MyApp)
    
    # Simulate User 1
    client1 = TestClient(server.app)
    res1 = client1.get("/")
    assert res1.status_code == 200
    sid1 = res1.cookies.get("htag_sid")
    assert sid1 is not None
    
    # Simulate User 2
    client2 = TestClient(server.app)
    res2 = client2.get("/")
    assert res2.status_code == 200
    sid2 = res2.cookies.get("htag_sid")
    assert sid2 is not None
    assert sid1 != sid2
    
    # Verify they have different instances in WebServer
    inst1 = server._get_instance(sid1)
    inst2 = server._get_instance(sid2)
    assert inst1 is not inst2
    assert isinstance(inst1, MyApp)
    assert isinstance(inst2, MyApp)

def test_single_instance_logic():
    """Verify that passing an instance shares it among all sids (backward compatibility)."""
    shared_app = MyApp()
    server = WebServer(shared_app)
    
    client1 = TestClient(server.app)
    res1 = client1.get("/")
    sid1 = res1.cookies.get("htag_sid")
    
    client2 = TestClient(server.app)
    res2 = client2.get("/")
    sid2 = res2.cookies.get("htag_sid")
    
    inst1 = server._get_instance(sid1)
    inst2 = server._get_instance(sid2)
    assert inst1 is inst2
    assert inst1 is shared_app

def test_on_instance_callback():
    """Verify that the on_instance callback is called exactly once per new instance."""
    initialized = []
    def my_init(inst):
        initialized.append(inst)
        inst.initialized = True
        
    server = WebServer(MyApp, on_instance=my_init)
    client = TestClient(server.app)
    
    # Trigger instance creation
    res = client.get("/")
    sid = res.cookies.get("htag_sid")
    inst = server._get_instance(sid)
    
    assert inst in initialized
    assert inst.initialized is True
    assert len(initialized) == 1
    
    # Retrieval should not trigger it again
    inst_again = server._get_instance(sid)
    assert len(initialized) == 1

def test_favicon_route():
    """Verify the silent favicon route exists."""
    server = WebServer(MyApp)
    client = TestClient(server.app)
    res = client.get("/favicon.ico")
    # It should return 200 (if logo exists) or 204 (if not)
    assert res.status_code in [200, 204]
