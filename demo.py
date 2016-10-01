#!/usr/bin/python
from parallelrpclib import ParallelServerProxy
from threading import Thread

import SocketServer
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler


class TestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/',)


class TestServer(SocketServer.ThreadingMixIn, SimpleXMLRPCServer):
    def __init__(self, port, handler=TestHandler):
        SimpleXMLRPCServer.__init__(self, ('localhost', port), handler)

        def quit():
            self.shutdown()
            return True

        self.register_introspection_functions()
        self.register_function(pow)
        self.register_function(quit)

    def run(self):
        self.server.serve_forever()


class TestWorker(Thread):
    def __init__(self, port, handler=TestHandler):
        Thread.__init__(self)
        self.server = TestServer(port, handler)
        self.daemon = True

    def run(self):
        self.server.serve_forever()


def doit():
    p = ParallelServerProxy([
        'http://localhost:9990/',
        'http://localhost:9991/'])

    print '%s' % p.pow(2, 2)

    TestWorker(9990).start()
    TestWorker(9991).start()

    print '%s' % p.pow(2, 2)
    print '%s' % p.quit()


if __name__ == '__main__':
    doit()
