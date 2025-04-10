# ADR: Token-Based Sharded Context Retrieval

## Status
Proposed

## Context
The Memory System requires substantial performance improvements when handling large repositories. Current implementation works well for small to medium codebases but becomes a bottleneck when processing repositories with thousands of files or large file metadata.

The performance issue stems from the associative matching process having to scan the entire global index for each context retrieval operation. For large repositories, this can potentially exceed memory constraints and cause performance degradation.

The key challenge is maintaining compatibility with the established architecture, which specifies that:
1. The Memory System must return all relevant matches without filtering or prioritization
2. The Memory System is not responsible for ranking or limiting results
3. The Memory System follows a read-only context model
4. All file paths must be absolute

## Decision
We will implement token-based sharded context retrieval in the Memory System with these key characteristics:

1. **Token-Based Sharding**: Rather than using file count, shards will be created based on estimated token counts, aligning with the model's context window constraints.

2. **Parallel Processing**: Shards will be processed in parallel using ThreadPoolExecutor to improve performance.

3. **Full Result Preservation**: All relevant matches from all shards will be aggregated and returned without arbitrary limits or filtering.

4. **Configuration Options**: The sharding behavior will be configurable through:
   - `enableSharding`: Toggle sharded retrieval on/off
   - `configureSharding`: Configure token size per shard and max shards
   - `configure`: Comprehensive configuration method

5. **Internal Implementation**: The sharding mechanism will be implemented as an internal optimization that maintains the existing public interface.

## Implementation Details

### Sharding Mechanism
1. During `updateGlobalIndex`, if sharding is enabled:
   - Estimate token count for each file's metadata
   - Create shards based on token count thresholds (not file count)
   - Ensure no shard exceeds the token size limit

2. For `getRelevantContextFor`, if sharding is enabled:
   - Process each shard in parallel using ThreadPoolExecutor
   - Perform associative matching within each shard
   - Aggregate all matches without filtering or prioritization
   - Return the complete set of results

### Token Estimation
Use a simple character-to-token ratio (default: 0.25, or 4 characters per token) to estimate token counts. This approximation is sufficient for sharding purposes and avoids dependencies on specific tokenizers.

### Configuration
```python
def configure(self, config: Dict[str, Any]) -> None:
    """Configure memory system behavior including sharding."""
    self._config.update(config)
    if self._config["shardingEnabled"] and any(k in config for k in ["tokenSizePerShard", "maxShards"]):
        self._update_shards()
```

## Consequences

### Positive
- **Improved Performance**: Significant speed improvement for large repositories
- **Scalability**: Support for repositories of any size within system resources
- **Memory Efficiency**: Better memory utilization through bounded shard sizes
- **Architectural Integrity**: Maintains existing interfaces and component boundaries
- **Full Result Preservation**: Returns all relevant matches without arbitrary limits

### Negative
- **Implementation Complexity**: Adds complexity with parallel processing
- **Configuration Overhead**: Introduces configuration requirements
- **Approximate Token Estimation**: Uses approximation rather than exact tokenization
- **Memory Usage**: May temporarily use more memory during parallel processing

## Alternatives Considered

### 1. Hierarchical Index
Creating a hierarchical index (by directory, file type, etc.) was considered but rejected because:
- It adds complexity without clear performance benefits
- Directory structure doesn't necessarily correlate with token counts
- It would make the implementation more brittle to repository structure changes

### 2. External Optimization Layer
Adding an external optimization layer was considered but rejected because:
- It would add an unnecessary component to the architecture
- It would complicate the integration between components
- Internal optimization achieves the same benefits without architectural changes

### 3. File Count Based Sharding
Sharding based on file count was initially considered but rejected because:
- File sizes and metadata sizes vary significantly
- Token count more directly relates to the performance bottleneck (context window)
- It could result in imbalanced shards in terms of computational work

## Implementation Phases

1. **Core Implementation**: Token-based sharding mechanism and configuration
2. **Parallel Processing**: ThreadPoolExecutor integration for parallel shard processing
3. **Testing & Validation**: Comprehensive testing with varying repository sizes
4. **Documentation**: Update documentation to reflect the new capability

## Compatibility

This enhancement maintains full compatibility with the existing Memory System interface. All changes are internal optimizations that don't affect the contract with other components.
