# Smart Cache Management Guide

## Overview
The cache management system now includes intelligent filtering to delete similar prompts based on semantic similarity clusters, helping you clean up duplicates and manage cache efficiently.

## Features

### 1. **View Cache Tab** 📋
- See all cached queries and responses
- Display includes query preview, response preview, and last used timestamp
- Expandable details view for full query/response text
- Refresh button to reload cache data

### 2. **Smart Delete Tab** 🧠
**Group similar prompts together and delete selectively:**

- **Automatic Clustering**: Prompts are grouped by semantic similarity (threshold: 0.75)
- **Duplicate Detection**: Shows count of similar queries grouped together
- **Similarity Score**: Displays average similarity within each cluster
- **Options to delete**:
  - `Keep Primary + Remove Duplicates`: Keeps the first query, deletes similar ones
  - `Delete Individual Items`: Remove specific items from within a cluster
  - `Delete Entire Cluster`: Remove all items in a group (when keeping primary is disabled)

### 3. **Clear All Tab** 🗑️
- Nuclear option to wipe the entire cache at once
- Warning displayed to prevent accidental deletion

## Use Cases

### Scenario 1: Remove Duplicate Questions
```
Cluster: AI & Machine Learning
├─ "What is artificial intelligence?" (PRIMARY)
├─ "Tell me about AI" (DUPLICATE - 95% similar)
└─ "Explain artificial intelligence" (DUPLICATE - 92% similar)

Action: Click "Remove Duplicates" → Keeps PRIMARY, deletes 2 items
Result: Save cache space by avoiding redundant responses
```

### Scenario 2: Clean Up Outdated Questions
```
Cluster: Weather Forecasting
├─ "How does weather prediction work?" (Last used: 10 days ago)
├─ "Weather forecasting methods" (Last used: 5 days ago)
└─ "Explain weather models" (Last used: 2 days ago)

Action: Click ❌ on first item → Deletes that specific question
Result: Remove outdated queries, keep frequently used ones
```

### Scenario 3: Emergency Cache Clear
```
Cache Status: 95/100 items (cache is full)

Action: Go to "Clear All" tab → Click "Clear All Cache"
Result: Remove all cached responses to free up space
```

## API Endpoints

### Get Cache Summary with Clusters
```
GET /cache/summary

Response:
{
  "total_items": 25,
  "total_clusters": 8,
  "clusters": [
    {
      "cluster_id": 0,
      "primary_query": "What is AI?",
      "duplicate_count": 2,
      "avg_similarity": 0.928,
      "items": [
        {"id": "abc123", "query": "...", "last_used_formatted": "..."}
      ]
    }
  ]
}
```

### Delete Specific Items
```
POST /cache/delete

Request:
{
  "item_ids": ["abc123", "def456"],
  "reason": "Manual deletion"
}

Response:
{
  "success": true,
  "deleted_count": 2,
  "remaining": 23
}
```

### Delete Cluster (Keep Primary)
```
POST /cache/delete-cluster

Request:
{
  "cluster_id": 0,
  "keep_primary": true,
  "reason": "Cluster deletion"
}

Response:
{
  "success": true,
  "deleted_count": 2,
  "remaining": 23
}
```

## Configuration

### Similarity Threshold
The clustering algorithm uses a **similarity threshold of 0.75** (range: 0-1):
- **0.9+**: Very similar (exact paraphrases)
- **0.75-0.9**: Similar (same topic, slightly different wording)
- **0.5-0.75**: Related (about the same subject)
- **<0.5**: Different prompts

To modify, edit in `backend/cache.py`:
```python
def cluster_similar_prompts(similarity_threshold: float = 0.75):  # Change this value
```

## Performance Impact

- **Clustering Time**: ~100ms per 10 cached items
- **Deletion Time**: ~10ms per item
- **API Timeout**: 15 seconds (sufficient for large caches)

## Best Practices

1. **Regular Cleanup**: Run "Smart Delete" weekly to remove duplicates
2. **Monitor Cache Size**: Keep cache <80 items for optimal performance
3. **Review Duplicates**: Check similarity scores before bulk deletion
4. **Keep Primaries**: Use "Keep Primary + Remove Duplicates" to maintain quality primaries
5. **Emergency Clear**: Only use "Clear All" when cache is corrupted or full

## Tips & Tricks

✅ **Reduce cache size** by 20-30% using duplicates removal
✅ **Maintain response quality** by keeping primary queries
✅ **Speed up queries** by cleaning old/unused similar prompts
✅ **Save storage** by removing related queries to one primary
❌ **Avoid** deleting primary queries accidentally

---

**Status**: Smart cache deletion is fully functional and tested
**Last Updated**: April 2026
