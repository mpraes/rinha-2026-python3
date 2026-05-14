echo "| Threshold | P99 | Failure Rate | Final Score | False Positives | False Negatives | HTTP Errors |"
echo "|-----------|-----|--------------|-------------|-----------------|-----------------|-------------|"
for threshold in 0.56 0.58 0.60 0.62 0.64 0.66; do
    docker compose down > /dev/null 2>&1
    FRAUD_THRESHOLD=$threshold API_IMAGE=rinha-api:local docker compose up -d > /dev/null 2>&1
    
    # Wait for ready
    until curl -sS http://localhost:9999/ready > /dev/null 2>&1; do
        sleep 1
    done

    k6 run test/test.js > /tmp/k6_threshold_$threshold.log 2>&1
    
    p99=$(jq -r '.metrics.http_req_duration.values."p(99)"' test/results.json)
    failure_rate=$(jq -r '.metrics.fraud_detection_failures.values.rate' test/results.json)
    final_score=$(jq -r '.metrics.final_score.values.value' test/results.json)
    false_positives=$(jq -r '.metrics.false_positives.values.count' test/results.json)
    false_negatives=$(jq -r '.metrics.false_negatives.values.count' test/results.json)
    http_errors=$(jq -r '.metrics.http_req_failed.values.passes' test/results.json)
    
    echo "| $threshold | $p99 | $failure_rate | $final_score | $false_positives | $false_negatives | $http_errors |"
done
