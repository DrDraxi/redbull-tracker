using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using RedBullTracker.Services;

namespace RedBullTracker.Tests;

public class ApiRedBullServiceTests
{
    private class StubHandler : HttpMessageHandler
    {
        private readonly Queue<HttpResponseMessage> _responses;
        public int CallCount { get; private set; }

        public StubHandler(params HttpResponseMessage[] responses)
        {
            _responses = new Queue<HttpResponseMessage>(responses);
        }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            CallCount++;
            return Task.FromResult(_responses.Dequeue());
        }
    }

    private class CapturingHandler : HttpMessageHandler
    {
        private readonly Action<HttpRequestMessage> _capture;
        private readonly HttpResponseMessage _response;

        public CapturingHandler(Action<HttpRequestMessage> capture, HttpResponseMessage response)
        {
            _capture = capture;
            _response = response;
        }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            _capture(request);
            return Task.FromResult(_response);
        }
    }

    private static HttpResponseMessage Json(string body, HttpStatusCode status = HttpStatusCode.OK)
        => new(status) { Content = new StringContent(body, Encoding.UTF8, "application/json") };

    [Fact]
    public async Task RefreshAsync_PopulatesByType()
    {
        var handler = new StubHandler(Json("""{"total":3,"by_type":{"default":2,"sugarfree":1},"updated_at":null}"""));
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");

        await svc.RefreshAsync();

        Assert.Equal(3, svc.Count);
        Assert.Equal(2, svc.ByType["default"]);
        Assert.Equal(1, svc.ByType["sugarfree"]);
        Assert.True(svc.IsReadOnly);
        Assert.False(svc.IsStale);
    }

    [Fact]
    public async Task RefreshAsync_OnError_MarksStale()
    {
        var handler = new StubHandler(new HttpResponseMessage(HttpStatusCode.InternalServerError));
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");

        await svc.RefreshAsync();

        Assert.True(svc.IsStale);
        Assert.Equal(0, svc.Count);
    }

    [Fact]
    public async Task RefreshAsync_AfterErrorThenSuccess_ClearsStale()
    {
        var handler = new StubHandler(
            new HttpResponseMessage(HttpStatusCode.InternalServerError),
            Json("""{"total":1,"by_type":{"default":1},"updated_at":null}""")
        );
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");

        await svc.RefreshAsync();
        Assert.True(svc.IsStale);

        await svc.RefreshAsync();
        Assert.False(svc.IsStale);
        Assert.Equal(1, svc.Count);
    }

    [Fact]
    public async Task RefreshAsync_NoChange_DoesNotFireEvent()
    {
        var handler = new StubHandler(
            Json("""{"total":2,"by_type":{"default":2},"updated_at":null}"""),
            Json("""{"total":2,"by_type":{"default":2},"updated_at":null}""")
        );
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");

        int events = 0;
        svc.CountChanged += (_, _) => events++;

        await svc.RefreshAsync();  // first refresh fires (empty -> populated)
        await svc.RefreshAsync();  // identical state, no fire

        Assert.Equal(1, events);
    }

    [Fact]
    public async Task AddCanAsync_Throws_BecauseReadOnly()
    {
        var handler = new StubHandler();
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");
        await Assert.ThrowsAsync<InvalidOperationException>(() => svc.AddCanAsync());
    }

    [Fact]
    public async Task RefreshAsync_SendsBearerHeader()
    {
        AuthenticationHeaderValue? captured = null;
        var handler = new CapturingHandler(req => captured = req.Headers.Authorization,
            Json("""{"total":0,"by_type":{},"updated_at":null}"""));
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "my-token");

        await svc.RefreshAsync();

        Assert.NotNull(captured);
        Assert.Equal("Bearer", captured!.Scheme);
        Assert.Equal("my-token", captured.Parameter);
    }
}
