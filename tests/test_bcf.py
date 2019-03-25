# -*- coding: utf-8 -*-
"""
Test module for bcf.
@author: kylez
"""
import json
import logging
import os

from httmock import HTTMock
from httmock import response
from httmock import urlmatch

from poseidon.controllers.bcf.bcf import BcfProxy
from poseidon.controllers.bcf.sample_state import span_fabric_state

logger = logging.getLogger('test')


class MockLogger:
    def __init__(self):
        self.logger = logger


cur_dir = os.path.dirname(os.path.realpath(__file__))
username = 'user'
password = 'pass'
cookie = 'cookie'


def mock_factory(regex, filemap):
    @urlmatch(netloc=regex)
    def mock_fn(url, request):
        if url.path == '/login':
            j = json.loads(request.body)
            assert j['user'] == username
            assert j['password'] == password
            headers = {'set-cookie': 'session_cookie={0}'.format(cookie)}
            r = response(headers=headers, request=request)
        elif url.path in filemap:
            with open(os.path.join(cur_dir, filemap[url.path])) as f:
                data = f.read().replace('\n', '')
            r = response(content=data, request=request)
        else:  # pragma: no cover
            raise Exception('Invalid URL: {0}' .format(url))
        return r
    return mock_fn


def mock_factory2(regex):
    @urlmatch(netloc=regex)
    def mock_fn(url, request):
        if url.path == '/data/controller/applications/bcf/tenant[name=%22TENANT%22]/segment[name=%22SEGMENT%22]/endpoint':
            with open(os.path.join(cur_dir, 'sample_endpoints2.json')) as f:
                data = f.read().replace('\n', '')
                data = json.loads(data)
            request_body = json.loads(request.body)
            if request_body['shutdown']:
                data[0]['state'] = 'Shut Down'
            else:
                data[0]['state'] = 'Active'
            data = json.dumps(data)
            r = response(content=data, request=request)
        elif url.path == '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]' and request.method == 'GET':
            data = json.dumps(span_fabric_state)
            r = response(content=data, request=request)
        elif url.path == '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]' and request.method == 'PUT':
            request_body = json.loads(request.body)
            span_fabric_state[0]['filter'] = request_body['filter']
            data = json.dumps(span_fabric_state)
            r = response(content=data, request=request)
        else:  # pragma: no cover
            raise Exception('Invalid URL: {0}'.format(url))
        return r
    return mock_fn


def test_BcfProxy():
    """
    Tests bcf
    """
    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
        '/data/controller/applications/bcf/span-fabric[name=%22empty%22][dest-interface-group=%22empty%22]': 'sample_span_fabric_empty.json',
    }
    proxy = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        endpoints = proxy.get_endpoints()
        assert endpoints
        switches = proxy.get_switches()
        assert switches
        tenants = proxy.get_tenants()
        assert tenants
        segments = proxy.get_segments()
        assert segments
        span_fabric = proxy.get_span_fabric()
        assert span_fabric
        span_fabric = proxy.get_span_fabric(span_name='SPAN_FABRIC')
        assert span_fabric
        span_fabric = proxy.get_span_fabric(
            span_name='empty', interface_group='empty')
        assert not span_fabric

    with HTTMock(mock_factory2(r'.*')):
        # Normally shutdown_endpoint does not return a value.
        # You should call get_endpoint() afterwards to verify that a shutdown request went through.
        # In addition, the mock endpoint generated does not check for duplicates.
        # TODO: ***This code below is temporary.***
        r = proxy.shutdown_endpoint(
            tenant='TENANT',
            segment='SEGMENT',
            endpoint_name='test',
            mac='00:00:00:00:00:00',
            shutdown=True)
        assert r
        r = proxy.shutdown_endpoint(
            tenant='TENANT',
            segment='SEGMENT',
            endpoint_name='test',
            mac='00:00:00:00:00:00',
            shutdown=False)
        assert r

        r = proxy.mirror_traffic(
            seq=2,
            mirror=True,
            tenant='TENANT',
            segment='SEGMENT')
        assert r
        r = proxy.mirror_traffic(seq=2, mirror=False)
        assert r

    def r(): return True
    r.text = ''
    r.status_code = 200
    r.url = 'asdf'

    # cover object
    assert r()

    BcfProxy.parse_json(r)

    proxy.session.cookies.clear_session_cookies()

    proxy.base_uri = 'http://jsonplaceholder.typicode.com'
    r = proxy.post_resource('posts')
    r.raise_for_status()
    r = proxy.request_resource(
        method='PUT',
        url='http://jsonplaceholder.typicode.com/posts/1')
    r.raise_for_status()


def test_format_endpoints():
    input_data = list([{'attachment-point': {'switch-interface': {'interface': 'ethernet16',
                                                                  'switch': 'leaf02'},
                                             'type': 'switch-interface'},
                        'attachment-point-state': 'learned',
                        'created-since': '2017-09-18T16:28:34.694Z',
                        'detail': 'true',
                        'interface': 'ethernet16',
                        'ip-address': [{'ip-address': '10.0.0.101',
                                        'ip-state': 'learned',
                                        'mac': 'f8:b1:56:fe:f2:de',
                                        'segment': 'prod',
                                        'tenant': 'FLOORPLATE'}],
                        'leaf-group': '00:00:f4:8e:38:16:a3:73',
                        'mac': 'f8:b1:56:fe:f2:de',
                        'nat-endpoint': False,
                        'remote': False,
                        'segment': 'prod',
                        'state': 'Active',
                        'switch': 'leaf02',
                        'tenant': 'FLOORPLATE',
                        'vlan': -1},
                       {'attachment-point': {'switch-interface': {'interface': 'ethernet42',
                                                                  'switch': 'leaf01'},
                                             'type': 'switch-interface'},
                        'attachment-point-state': 'learned',
                        'created-since': '2017-07-11T23:56:23.888Z',
                        'detail': 'true',
                        'interface': 'ethernet42',
                        'leaf-group': '00:00:f4:8e:38:16:b3:73',
                        'mac': '20:4c:9e:5f:e3:a3',
                        'nat-endpoint': False,
                        'remote': False,
                        'segment': 'to-core-router',
                        'state': 'Active',
                        'switch': 'leaf01',
                        'tenant': 'EXTERNAL',
                        'vlan': -1}])

    output = BcfProxy.format_endpoints(input_data)
    answer = list([{'mac': 'f8:b1:56:fe:f2:de', 'segment': 'leaf02',
                    'tenant': 'FLOORPLATE', 'name': None, 'active': 1,
                    'port': 'ethernet16', 'ipv4': '10.0.0.101', 'ipv6': 0}])
    assert str(answer) == str(output)


def test_get_byip():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.logger = MockLogger().logger

        def get_endpoints(self):
            return self.endpoints

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
    }
    proxy = None
    endpoints = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        endpoints = proxy.get_endpoints()
    bcf.endpoints = endpoints
    ret_val = bcf.get_byip('10.0.0.1')
    answer = list([{'ip-address': '10.0.0.1',
                    'ip-state': 'learned',
                    'mac': '00:00:00:00:00:01',
                    'segment': 'poseidon',
                    'tenant': 'poseidon',
                    'name': None}])
    assert str(answer) == str(ret_val)


def test_get_bymac():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.logger = MockLogger().logger
            self.trust_self_signed_cert = True

        def get_endpoints(self):
            return self.endpoints

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
    }
    proxy = None
    endpoints = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        endpoints = proxy.get_endpoints()
    bcf.endpoints = endpoints
    ret_val = bcf.get_bymac('00:00:00:00:00:01')
    answer = list([{'mac': '00:00:00:00:00:01', 'name': None,
                    'tenant': 'poseidon', 'segment': 'poseidon', 'attachment-point': {'switch-interface': {'interface': 'ethernet01', 'switch': 'Leaf2'}, 'type': 'switch-interface'}}])
    assert str(answer) == str(ret_val)


def test_shutdown_ip():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.logger = MockLogger().logger

        def get_endpoints(self):
            return self.endpoints

        def shutdown_endpoint(self, tenant, segment, name, mac, shutdown):
            pass

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
    }
    proxy = None
    endpoints = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        endpoints = proxy.get_endpoints()

    bcf.endpoints = endpoints
    ret_val = bcf.shutdown_ip('10.0.0.1')
    answer = list([{'ip-address': '10.0.0.1',
                    'ip-state': 'learned',
                    'mac': '00:00:00:00:00:01',
                    'segment': 'poseidon',
                    'tenant': 'poseidon',
                    'name': None}])

    assert str(answer) == str(ret_val)

    ret_val = bcf.shutdown_ip('10.0.0.1', mac_addr='00:00:00:00:00:01')
    answer = list([{'mac': '00:00:00:00:00:01',
                    'name': None,
                    'tenant': 'poseidon',
                    'segment': 'poseidon', 'attachment-point': {'switch-interface': {'interface': 'ethernet01', 'switch': 'Leaf2'}, 'type': 'switch-interface'}}])

    assert str(answer) == str(ret_val)


def test_get_highest():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.span_fabric = None
            self.logger = MockLogger().logger

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
    }
    proxy = None
    endpoints = None
    span_fabric = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        proxy.check_connection()
        endpoints = proxy.get_endpoints()
        span_fabric = proxy.get_span_fabric()

    bcf.endpoints = endpoints
    bcf.span_fabric = span_fabric
    ret_val = bcf.get_highest(span_fabric)
    answer = 3

    assert answer == ret_val


def test_get_highest_no_filter():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.span_fabric = None
            self.logger = MockLogger().logger

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric_empty.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric_empty.json',
    }
    proxy = None
    endpoints = None
    span_fabric = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        proxy.check_connection()
        endpoints = proxy.get_endpoints()
        span_fabric = proxy.get_span_fabric()

    bcf.endpoints = endpoints
    bcf.span_fabric = span_fabric
    ret_val = bcf.get_highest(span_fabric)
    answer = 1

    assert answer == ret_val


def test_get_seq_by_ip():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.span_fabric = None
            self.logger = MockLogger().logger
            self.trust_self_signed_cert = True

        def get_span_fabric(self):
            return self.span_fabric

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
    }
    proxy = None
    endpoints = None
    span_fabric = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        endpoints = proxy.get_endpoints()
        span_fabric = proxy.get_span_fabric()

    bcf.endpoints = endpoints
    bcf.span_fabric = span_fabric
    ret_val = bcf.get_seq_by_ip('10.0.0.2')
    answer = list()
    assert answer == ret_val


def test_get_seq_by_mac():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.span_fabric = None
            self.logger = MockLogger().logger
            self.trust_self_signed_cert = True

        def get_endpoints(self):
            return self.endpoints

        def get_span_fabric(self):
            return self.span_fabric

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
    }
    proxy = None
    endpoints = None
    span_fabric = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        endpoints = proxy.get_endpoints()
        span_fabric = proxy.get_span_fabric()

    bcf.endpoints = endpoints
    bcf.span_fabric = span_fabric
    ret_val = bcf.get_seq_by_mac('00:00:00:00:00:02')
    # TODO this test needs to actually do something with the switch/interface
    answer = []
    assert answer == ret_val


def test_mirror_mac():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.span_fabric = None
            self.trust_self_signed_cert = True
            self.base_uri = None
            self.logger = MockLogger().logger

        def get_bymac(self, mac):
            return [{'mac': mac, 'name': 'foo', 'tenant': 'foo', 'segment': 'foo', 'attachment-point': 'foo'}]

        def get_span_fabric(self):
            return self.span_fabric

        def bad_get_highest(self, spanFabric):
            return None

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
    }

    proxy = None
    endpoints = None
    span_fabric = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        endpoints = proxy.get_endpoints()
        span_fabric = proxy.get_span_fabric()

    bcf.endpoints = endpoints
    bcf.span_fabric = span_fabric
    ret_val = bcf.mirror_mac('00:00:00:00:00:02', None, None)

    bcf.get_highest = bcf.bad_get_highest
    ret_val = bcf.mirror_mac('00:00:00:00:00:02', None, None)


def test_unmirror_mac():

    class MockBcfProxy(BcfProxy):

        def __init__(self):
            self.endpoints = None
            self.span_fabric = None
            self.logger = MockLogger().logger
            self.trust_self_signed_cert = True
            self.base_uri = None

        def get_endpoints(self):
            return self.endpoints

        def get_span_fabric(self):
            return self.span_fabric

    bcf = MockBcfProxy()

    filemap = {
        '/data/controller/applications/bcf/info/fabric/switch': 'sample_switches.json',
        '/data/controller/applications/bcf/info/endpoint-manager/tenant': 'sample_tenants.json',
        '/data/controller/applications/bcf/info/endpoint-manager/segment': 'sample_segments.json',
        '/data/controller/applications/bcf/info/endpoint-manager/endpoint': 'sample_endpoints.json',
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22]': 'sample_span_fabric.json',
        # %22 = url-encoded double quotes
        '/data/controller/applications/bcf/span-fabric[name=%22SPAN_FABRIC%22][dest-interface-group=%22INTERFACE_GROUP%22]': 'sample_span_fabric.json',
    }
    proxy = None
    endpoints = None
    span_fabric = None
    controller = {'URI': 'http://localhost',
                  'USER': username, 'PASS': password, 'SPAN_FABRIC_NAME': 'SPAN_FABRIC', 'INTERFACE_GROUP': 'INTERFACE_GROUP', 'TRUST_SELF_SIGNED_CERT': True}
    with HTTMock(mock_factory(r'.*', filemap)):
        proxy = BcfProxy(controller, 'login')

        endpoints = proxy.get_endpoints()
        span_fabric = proxy.get_span_fabric()

    bcf.endpoints = endpoints
    bcf.span_fabric = span_fabric
    ret_val = bcf.unmirror_mac('00:00:00:00:00:01', None, None)
