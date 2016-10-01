## An efficient parallel XML-RPC client

This module is a enhancement for `xmlrpclib` which allows the client to
efficiently make multiple (identical) RPC requests in parallel.

There are currently three strategies implemented for parallel requests,
perhaps we'll have more in the future. In particular, it would be nice
to have a proper event-loop based implementation.


### Basic usage

    import parallelrpclib

    psp = parallelrpclib.ParallelServerProxy([
        'http://localhost:1234/xmlrpc/',
        'http://server.com/xmlrpc/',
        server_object])

    # Invoke do_something() on all three servers in parallel
    for result, exc in psp.do_something(with, args):
        if exc is None:
            # Success! Do something with result.
        else:
            # Uh oh, we have an exception...


#### Specifying Servers

The `ParallelServerProxy` can be instanciated with a list of URLs,
classes, or a mixture of both. URLs will be internally converted into a
class similar to `xmlrpclib.ServerProxy`, using a strategy which depends
on which kind of parallelism is requested.


#### Invoking Methods

Just like `xmlrpclib.ServerProxy`, the `ParallelServerProxy` objects
will accept any method name and attempt to pass it on to the servers. 


#### Return Codes and Error Handling

Error handling mostly inherited from `xmlrpclib`, except any raised
execeptions are caught and returned to the caller in the list of return
codes.

The return value of any method called is therefore a list of `(response,
exception)` tuples, where the response or exception is always None.


### Parallelism strategies

#### Threaded parallelism

Example:

    from parallellrpc import ThreadedParallelServerProxy

    psp = ThreadedParallelServerProxy(['http://server/rpc/', ...])
    results = psp.do_stuff()

In this model a new thread is created for each request and all run in
parallel. Results are returned when all threads have completed.

This method is not particularly efficient on the client side, as each
outgoing request is formatted independently and creating threads has a
fair bit of overhead. This method minimizes network latency and load on
the remote servers.

#### Two-stage parallelism

Example:

    from parallellrpc import TwoStageParallelServerProxy

    psp = TwoStageParallelServerProxy(['http://server/rpc/', ...])
    results = psp.do_stuff()

Parallelism is achieved by submitting all the work requests to the
servers before reading any responses. Results are returned when all
responses have been read.

This method minimizes load on the client, but may take more time (wall
clock time) if there is noticable network latency. For responses larger
than OS/network buffers, this method may also consume more resources on
the server side by blocking or holding connections open longer than
necessary.

Note that two-stage parallelism is only available to servers specified
as URLs, if any servers are specified as objects they will be invoked in
order (or in threads if using the Hybrid method discussed below).

#### Hybrid parallelism

Example:

    from parallellrpc import HybridParallelServerProxy

    psp = HybridParallelServerProxy(['http://server/rpc/', ...])
    results = psp.do_stuff()

This method combines threading and two-stage parallelism. The two-stage
approach is used by default for servers on `localhost`, threads are used
for everything else.

This is currently the default `ParallelServerProxy` implementation.

To manually enable two-stage parallelism for a non-localhost server,
by instanciating your own `TwoStageServerProxy` and passing in as server
instead of an URL:

    from parallellrpc import HybridParallelServerProxy
    from parallellrpc import TwoStageServerProxy

    psp = HybridParallelServerProxy([
        'http://server/rpc/',
        TwoStageServerProxy('http://nearbyhost.com/rpc/'),
        ... ])

    results = psp.do_stuff()


### TODO

   * Add support for HTTPS to `TwoStageServerProxy`.

