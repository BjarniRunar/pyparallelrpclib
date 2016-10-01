#!/usr/bin/python
import time
from parallelrpclib import *
from multiprocessing import Process

import SocketServer
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler


class TestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/',)


class TestServer(SocketServer.ThreadingMixIn, SimpleXMLRPCServer):
    daemon_threads = True

    def __init__(self, port, handler=TestHandler):
        SimpleXMLRPCServer.__init__(self, ('localhost', port), handler,
                                    logRequests=False)

        def quit():
            self.shutdown()
            return True

        self.register_introspection_functions()
        self.register_function(pow)
        self.register_function(quit)

    def run(self):
        self.server.serve_forever()


class TestWorker(Process):
    def __init__(self, port, handler=TestHandler):
        Process.__init__(self)
        self.server = TestServer(port, handler)
        self.daemon = True

    def run(self):
        self.server.serve_forever()


class DummyServer:
    def pow(s, a, b):
        return pow(a, b)

    def quit(s):
        pass


def doit():

    TestWorker(9990).start()
    TestWorker(9991).start()
    TestWorker(9992).start()

    for proxyclass in (
            PretendParallelServerProxy,
            HybridParallelServerProxy,
            ThreadedParallelServerProxy,
            TwoStageParallelServerProxy):

        p = proxyclass([  # DummyServer(),
            'http://localhost:9990/',
            'http://localhost:9991/',
            'http://localhost:9992/'])

        print '***** %s *****' % p
        t0 = time.time()
        print ' Last result: %s' % [list(p.pow(i, 3)) for i in range(0, 1000)][-1]
        t1 = time.time()
        print ' Time: %.5fs (%.5fs/remote)' % (t1 - t0, (t1-t0)/3000)

    print 'Shutting down: %s' % list(p.quit())

if __name__ == '__main__':
    doit()
