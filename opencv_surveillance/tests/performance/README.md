# Performance Load Testing with Locust

This directory contains load testing configurations for OpenEye using Locust.

## Installation

```bash
cd opencv_surveillance
pip install locust
```

## Quick Start

### 1. Start the OpenEye Backend

```bash
cd opencv_surveillance
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 2. Run Load Test with Web UI

```bash
# From opencv_surveillance directory
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser to configure and start the test.

### 3. Run Headless Load Test

```bash
# 100 users, spawn 10 per second, run for 5 minutes
locust -f tests/performance/locustfile.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless
```

### 4. Generate HTML Report

```bash
locust -f tests/performance/locustfile.py \
    --host=http://localhost:8000 \
    --users 50 \
    --spawn-rate 5 \
    --run-time 2m \
    --headless \
    --html performance_report.html
```

## User Classes

### OpenEyeUser (Normal User)
Simulates typical user behavior with weighted tasks:
- **Weight 5**: List recordings (most common)
- **Weight 4**: Get face history
- **Weight 3**: Filter recordings
- **Weight 2**: List cameras, motion events, analytics
- **Weight 1**: Individual camera details, clusters

**Usage**: General load testing
```bash
locust -f tests/performance/locustfile.py OpenEyeUser
```

### HeavyUser (Stress Testing)
Performs expensive operations:
- Storage statistics
- Motion statistics
- Face detection statistics

**Usage**: Test system under heavy load
```bash
locust -f tests/performance/locustfile.py HeavyUser --users 20
```

### ReadOnlyUser (Mobile/API Clients)
Fast, lightweight operations:
- Quick camera status checks
- Cached analytics summaries
- Health checks

**Usage**: Test high-frequency, low-impact requests
```bash
locust -f tests/performance/locustfile.py ReadOnlyUser --users 200
```

## Test Scenarios

### Scenario 1: Normal Usage (Recommended)
Simulates 50-100 concurrent users with typical behavior patterns.

```bash
locust -f tests/performance/locustfile.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 10m \
    --headless \
    --html normal_usage.html
```

**Expected Results**:
- Average response time: < 100ms
- 95th percentile: < 500ms
- Error rate: < 0.1%

### Scenario 2: Stress Test
Tests system limits with heavy operations.

```bash
locust -f tests/performance/locustfile.py HeavyUser \
    --host=http://localhost:8000 \
    --users 50 \
    --spawn-rate 5 \
    --run-time 5m \
    --headless \
    --html stress_test.html
```

**Expected Results**:
- Average response time: < 500ms
- 95th percentile: < 2000ms
- No timeouts or 500 errors

### Scenario 3: High Concurrency (Mobile/API)
Tests system with many lightweight requests.

```bash
locust -f tests/performance/locustfile.py ReadOnlyUser \
    --host=http://localhost:8000 \
    --users 500 \
    --spawn-rate 50 \
    --run-time 5m \
    --headless \
    --html high_concurrency.html
```

**Expected Results**:
- Average response time: < 50ms (cached endpoints)
- 95th percentile: < 200ms
- High cache hit rate

### Scenario 4: Mixed Workload
Simulates realistic mix of user types.

```bash
# Terminal 1: Normal users
locust -f tests/performance/locustfile.py OpenEyeUser \
    --host=http://localhost:8000 \
    --users 80 \
    --spawn-rate 10 \
    --master

# Terminal 2: Heavy users
locust -f tests/performance/locustfile.py HeavyUser \
    --host=http://localhost:8000 \
    --users 10 \
    --spawn-rate 2 \
    --worker

# Terminal 3: Mobile users
locust -f tests/performance/locustfile.py ReadOnlyUser \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 20 \
    --worker
```

## Monitoring During Tests

### 1. Performance Metrics API
Monitor real-time performance while load testing:

```bash
# Summary
curl http://localhost:8000/api/metrics/performance/summary | jq

# Slow endpoints
curl http://localhost:8000/api/metrics/performance/slow | jq

# Recent requests
curl http://localhost:8000/api/metrics/performance/recent?limit=50 | jq
```

### 2. System Resources
Monitor server resources:

```bash
# CPU and memory
htop

# Database connections
lsof -i :8000

# Network connections
netstat -an | grep 8000
```

### 3. Backend Logs
Watch for slow request warnings:

```bash
tail -f server.log | grep "Slow request"
```

## Tag-Based Testing

Run tests for specific features using tags:

```bash
# Test only recording endpoints
locust -f tests/performance/locustfile.py --tags recordings

# Test cached endpoints only
locust -f tests/performance/locustfile.py --tags analytics

# Exclude expensive operations
locust -f tests/performance/locustfile.py --exclude-tags stats
```

## Interpreting Results

### Key Metrics

**Response Time**:
- **Good**: < 100ms average, < 500ms 95th percentile
- **Acceptable**: < 500ms average, < 2000ms 95th percentile
- **Poor**: > 500ms average, > 2000ms 95th percentile

**Error Rate**:
- **Good**: < 0.1%
- **Acceptable**: < 1%
- **Poor**: > 1%

**Requests per Second (RPS)**:
- **Light Load**: < 100 RPS
- **Moderate Load**: 100-500 RPS
- **Heavy Load**: > 500 RPS

### Common Issues

**High Response Times**:
- Check database query performance
- Verify indexes are created (`sqlite3 surveillance.db ".indexes"`)
- Monitor cache hit rates
- Check for N+1 queries

**High Error Rate**:
- Review backend logs for exceptions
- Check database connection pool
- Verify authentication is working
- Monitor rate limiting

**Timeouts**:
- Increase timeout in Locust: `--timeout 30`
- Check for blocking operations
- Review slow request logs
- Scale backend resources

## Best Practices

1. **Warm Up Period**: Let the system warm up for 1-2 minutes before measuring
2. **Realistic Data**: Test with production-like data volumes
3. **Monitor Everything**: Watch metrics, logs, and system resources
4. **Iterate**: Start small (10 users), gradually increase
5. **Document Results**: Save HTML reports for comparison
6. **Test After Changes**: Run load tests after performance improvements

## Example Test Report Analysis

After running a test, check:

1. **Response Time Distribution**: Should be left-skewed (most requests fast)
2. **Failure Rate**: Should be near 0%
3. **Requests/Second**: Should scale linearly with users (up to a point)
4. **Endpoint Breakdown**: Identify slowest endpoints
5. **Cache Effectiveness**: Compare cached vs uncached endpoint times

## CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/performance-test.yml
- name: Run Performance Tests
  run: |
    cd opencv_surveillance
    locust -f tests/performance/locustfile.py \
      --host=http://localhost:8000 \
      --users 50 \
      --spawn-rate 5 \
      --run-time 2m \
      --headless \
      --html performance_report.html \
      --csv performance_results

    # Fail if average response time > 500ms
    python scripts/check_performance.py performance_results_stats.csv
```

## Troubleshooting

**Locust not found**:
```bash
pip install locust
```

**Connection refused**:
```bash
# Make sure backend is running
curl http://localhost:8000/api/health
```

**Authentication errors**:
```bash
# Verify admin credentials
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

**Too many open files**:
```bash
# Increase file descriptor limit
ulimit -n 10000
```

## Next Steps

After analyzing load test results:

1. **Identify Bottlenecks**: Use metrics API to find slow endpoints
2. **Add Indexes**: Check PERFORMANCE_OPTIMIZATION_GUIDE.md
3. **Tune Caching**: Adjust TTL for frequently accessed data
4. **Optimize Queries**: Review slow queries in logs
5. **Scale Resources**: Add more workers/databases if needed
