import copy
import xmlrpclib
import threading

from xmlrpclib import Fault


class UnknownProtocolError(IOError):
    pass


class TwoStageTransport(xmlrpclib.Transport):
    """
    This is an enhanced xmlrpclib.Transport that allows requests to happen
    in two stages. First we send all the bits over the wire and then we
    read the response and parse it later on.
    """
    def __init__(self, *args, **kwargs):
        xmlrpclib.Transport.__init__(self, *args, **kwargs)
        self._lock = threading.Lock()
        self._seq = 0

    def start_request(self, host, handler, request_body, verbose=0):
        with self._lock:
            self._seq += 1
            h = self.make_connection(host)
            if verbose:
                h.set_debuglevel(1)

            try:
                self.send_request(h, handler, request_body)
                self.send_host(h, host)
                self.send_user_agent(h)
                self.send_content(h, request_body)
                return (h, verbose, self._seq)
            except Fault:
                raise
            except:
                self.close()
                raise

    def finish_request(self, state):
        with self._lock:
            h, verbose, seq = state
            assert(seq == self._seq)
            try:
                response = h.getresponse(buffering=True)
                if response.status == 200:
                    self.verbose = verbose
                    return self.parse_response(response)
            except Fault:
                raise
            except:
                self.close()
                raise


class TwoStageServerProxy(object):
    """
    A re-implementation of xmlrpclib.ServerProxy that makes requests
    in two stages; the first connect and write, the second reads.
    """
    def __init__(self, uri, transport=None, encoding=None, verbose=0,
                 allow_none=0, use_datetime=0, context=None):
        if isinstance(uri, unicode):
            uri = uri.encode('utf-8')

        import urllib
        type, uri = urllib.splittype(uri)
        if type not in ('http', ):
            raise UnknownProtocolError("unsupported XML-RPC protocol")

        self.host, self.handler = urllib.splithost(uri)
        if not self.handler:
            self.handler = '/RPC2'

        assert(transport is None)
        transport = TwoStageTransport(use_datetime=use_datetime)

        self.transport = transport
        self.encoding = encoding
        self.verbose = verbose
        self.allow_none = allow_none

    def close(self):
        self.transport.close()

    def request_format(self):
        return (self.encoding, self.allow_none)

    def make_request(self, methodname, params):
        return xmlrpclib.dumps(
            params, methodname,
            encoding=self.encoding,
            allow_none=self.allow_none)

    def start_request(self, request):
        try:
            return self.transport.start_request(
                self.host, self.handler, request, verbose=self.verbose)
        except Exception as exc:
            return exc

    def finish_request(self, state):
        if isinstance(state, Exception):
            return (None, state)
        try:
            response = self.transport.finish_request(state)
            if len(response) == 1:
                return (response[0], None)
            return (response, None)
        except Exception as exc:
            return (None, exc)

    def request(self, methodname, params):
        return (
            self.finish_request(
                self.start_request(
                    self.make_request(methodname, params))))


def _make_psp(kind, handle_request, tssp_localhost_only=False, doc=''):

    class _ParallelServerProxy(object):
        __doc__ = doc
        __KIND = kind

        def __init__(self, servers, **kwargs):
            self.__proxies = []
            tssp_lo = tssp_localhost_only
            if 'tssp_localhost_only' in kwargs:
                kwargs = copy.copy(kwargs)
                tssp_lo = kwargs['tssp_localhost_only']
                del kwargs['tssp_localhost_only']
            for s in servers:
                if isinstance(s, str):
                    if ((not tssp_lo) or
                            ('://localhost' in s) or
                            ('://127.0.0.' in s) or
                            ('://::1/' in s)):
                        try:
                            s = TwoStageServerProxy(s, **kwargs)
                        except UnknownProtocolError:
                            s = xmlrpclib.ServerProxy(s, **kwargs)
                    else:
                        s = xmlrpclib.ServerProxy(s, **kwargs)
                self.__proxies.append(s)

        def __close(self):
            for p in self.__proxies:
                p.__close()

        def __repr__(self):
            return (
                "<%sParallelServerProxy for %d servers>"
                % (self.__KIND, len(self.__proxies)))

        __str__ = __repr__

        def __request(self, methodname, params):
            return handle_request(self.__proxies, methodname, params)

        def __getattr__(self, name):
            return xmlrpclib._Method(self.__request, name)

    return NewParallelServerProxy


def _sequential_request(proxy, methodname, params, retry_list):
    try:
        if isinstance(proxy, TwoStageServerProxy):
            return (proxy.request(methodname, params), None)
        else:
            return (getattr(proxy, methodname)(*params), None)
    except Exception as exc:
        return (None, exc)


def _sequential_requests(proxies, methodname, params):
    return [_sequential_request(p, methodname, params, None) for p in proxies]


def _threaded_requests(proxies, methodname, params):
    results = []
    threads = []

    def runit(p):
        results.append(_sequential_request(p, methodname, params, None))

    for p in proxies:
        threads.append(threading.Thread(target=runit, args=(p,)))
        threads[-1].start()
    for t in threads:
        t.join()

    return results


def _two_stage_requests(proxies, methodname, params,
                        fallback=_sequential_requests):
    started = []
    tssps = [p for p in proxies if isinstance(p, TwoStageServerProxy)]
    if tssps:
        others = [p for p in proxies if not isinstance(p, TwoStageServerProxy)]
        formats = {}
        for p in tssps:
            fmt = p.request_format()
            if fmt not in formats:
                formats[fmt] = p

        for fmt, p in list(formats.iteritems()):
            formats[fmt] = p.make_request(methodname, params)

        for p in tssps:
            r = p.start_request(formats[p.request_format()])
            started.append((p, r))
    else:
        others = proxies

    if others:
        results = fallback(others, methodname, params)
    else:
        results = []

    results.extend(p.finish_request(r) for (p, r) in started)
    return results


def _hybrid_requests(proxies, methodname, params):
    return _two_stage_requests(proxies, methodname, params,
                               fallback=_threaded_requests)


PretendParallelServerProxy = _make_psp(
    "Pretend",
    _sequential_requests,
    doc="""\
This is a trivial sequential (not actually parallel) implementation
of the ParallelServerProxy API, as a reference or for testing.
""")


ThreadedParallelServerProxy = _make_psp(
    "Threaded",
    _threaded_requests,
    doc="""\
A ParallelServerProxy that uses threads to run requests in parallel.
""")


TwoStageParallelServerProxy = _make_psp(
    "TwoStage",
    _two_stage_requests,
    doc="""\
A ParallelServerProxy that uses the network for parallelization,
by sending all requests before reading any responses.
""")


HybridParallelServerProxy = _make_psp(
    "Hybrid",
    _hybrid_requests,
    tssp_localhost_only=True,
    doc="""\
A ParallelServerProxy that uses the network for parallelization
when possible, falling back to threads otherwise.
""")


ParallelServerProxy = HybridParallelServerProxy
