import copy
import select
import threading
import xmlrpclib

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

    def get_sockfd(self, state):
        with self._lock:
            h, verbose, seq = state
            assert(seq == self._seq)
            return h.sock

    def is_ready(self, state):
        try:
            sock = self.get_sockfd(state)
            r, w, e = select.select([sock], [], [sock], 0)
            return (len(r) + len(e) > 0)
        except (OSError, IOError):
            return True

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

    def get_sockfd(self, state):
        if isinstance(state, Exception):
            return None
        return self.transport.get_sockfd(state)

    def is_ready(self, state):
        if isinstance(state, Exception):
            return True
        return self.transport.is_ready(state)

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

    return _ParallelServerProxy


def _sequential_request(proxy, methodname, args):
    try:
        if isinstance(proxy, TwoStageServerProxy):
            return proxy.request(methodname, args)
        else:
            return (getattr(proxy, methodname)(*args), None)
    except Exception as exc:
        return (None, exc)


def RunSequentialJobs(jobs):
    """
    Run a list of (object, methodname, arg_list) jobs in order.
    """
    return (_sequential_request(p, m, a) for p, m, a in jobs)


def _sequential_requests(proxies, methodname, args):
    return RunSequentialJobs((p, methodname, args) for p in proxies)


def RunThreadedJobs(jobs):
    """
    Run a list of (object, methodname, arg_list) jobs in parallel,
    each in a thread of its own.
    """
    results = []
    threads = []

    def runit(p, m, a):
        results.append(_sequential_request(p, m, a))

    for p, m, a in jobs:
        threads.append(threading.Thread(target=runit, args=(p, m, a)))
        threads[-1].start()
    for t in threads:
        t.join()
        while results:
            yield results.pop(0)


def _threaded_requests(proxies, methodname, args):
    return RunThreadedJobs((p, methodname, args) for p in proxies)


def RunTwoStageJobs(jobs, fallback=RunSequentialJobs):
    """
    Run a list of (object, methodname, arg_list) jobs in parallel,
    using the network for parallelization whenever possible.
    """
    started = []
    tsjs = [j for j in jobs if isinstance(j[0], TwoStageServerProxy)]
    if tsjs:
        others = [j for j in jobs if not isinstance(j[0], TwoStageServerProxy)]
        formats = {}
        for p, m, a in tsjs:
            fmt = (m, a, p.request_format())
            if fmt not in formats:
                formats[fmt] = p

        for fmt, p in list(formats.iteritems()):
            formats[fmt] = p.make_request(fmt[0], fmt[1])

        for p, m, a in tsjs:
            r = p.start_request(formats[(m, a, p.request_format())])
            started.append((p, r))
    else:
        others = proxies

    if others:
        for result in fallback(others):
            yield result

    socklist = {}
    for pr in started:
        sockfd = pr[0].get_sockfd(pr[1])
        if sockfd is not None:
            socklist[sockfd] = pr

    while socklist:
        r, w, e = select.select(socklist.keys(), [], socklist.keys())
        for k in set(r + e):
            p, r = pr = socklist[k]
            started.remove(pr)
            del socklist[k]
            yield p.finish_request(r)

    for (p, r) in started:
        yield p.finish_request(r)


def _two_stage_requests(proxies, methodname, params):
    return RunTwoStageJobs([(p, methodname, params) for p in proxies])


def _hybrid_requests(proxies, methodname, params):
    return RunTwoStageJobs([(p, methodname, params) for p in proxies],
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
A ParallelServerProxy that uses either the network or threads to
run jobs in parallel.

The network is only used for parallelization for servers running
on localhost, unless tssp_localhost_only=False is given on init.
""")


ParallelServerProxy = HybridParallelServerProxy
