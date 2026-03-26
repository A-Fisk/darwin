# Citation Verification System

The Darwin Citation Verification System ensures that all scientific claims in generated hypotheses are properly supported by relevant citations from the literature context.

## Overview

The system consists of four main components:

1. **Citation Parser** (`citation_parser.py`) - Analyzes text to identify claims requiring citations
2. **Citation Verifier** (`citation_verifier.py`) - Verifies claims against available literature
3. **Citation Logger** (`citation_logger.py`) - Provides append-only logging for failures and successes
4. **Citation Pipeline** (`citation_pipeline.py`) - Integrates verification into Darwin workflow

## Key Features

### Sentence-Level Analysis
- Parses text into individual sentences with position tracking
- Identifies different types of claims (empirical, statistical, factual, recent advancements)
- Extracts keywords for matching against literature

### Citation Verification
- Verifies existing citations actually support the claims made
- Finds available literature that could support uncited claims
- Calculates confidence scores for verification results
- Provides detailed explanations for verification outcomes

### Append-Only Failure Logging
- Logs all citation verification events to persistent files
- Tracks failure patterns, retry attempts, and final outcomes
- Provides statistics for analyzing citation quality over time
- Thread-safe logging for concurrent agent operations

### Real-Time Integration
- Integrates seamlessly with Darwin's existing agent workflow
- Provides hooks for generation, reflection, and meta-review agents
- Offers configurable enforcement levels (warn vs. reject)
- Enables citation quality assessment in hypothesis scoring

## Usage

### Basic Verification

```python
from darwin.citation_pipeline import get_citation_pipeline

# Verify a single hypothesis
pipeline = get_citation_pipeline()
results = pipeline.verify_hypothesis(
    hypothesis=hypothesis_dict,
    literature_context=literature_list,
    agent_name="generation",
    iteration=1
)

# Generate citation quality report
report = pipeline.get_citation_report(results)
print(f"Citation score: {report['overall_score']:.2f}")
```

### Integration with Darwin Agents

```python
from darwin.citation_integration import create_citation_verification_middleware

# Apply to existing agents
middleware = create_citation_verification_middleware()
enhanced_generation = middleware["generation_enhancer"](original_generation_func)
enhanced_reflection = middleware["reflection_enhancer"](original_reflection_func)
```

### Configuration

Set environment variables to control behavior:

```bash
# Enable strict citation enforcement (reject uncited claims)
export DARWIN_ENFORCE_CITATIONS=true

# Enable citation quality assessment in scoring
export DARWIN_ASSESS_CITATIONS=true

# Enable failure logging
export DARWIN_CITATION_LOGGING=true
```

### Command Line Interface

```bash
# Verify citations in text
darwin-citations verify --text "Studies show improvement." --literature papers.json

# View failure statistics
darwin-citations stats --days 30

# Configure citation verification
darwin-citations config --enable

# Run tests
darwin-citations test --smoke-test
```

## Citation Requirements

### Claims Requiring Citations

1. **Empirical Claims**: "Studies show...", "Research indicates...", "Evidence suggests..."
2. **Statistical Claims**: Numbers, percentages, significance values, correlations
3. **Factual Assertions**: References to established mechanisms, documented processes
4. **Recent Advancements**: "Recent...", "Latest...", "State-of-the-art..."

### Citation Formats

The system recognizes multiple citation formats:
- Inline references: `[paper_id]` or `[smith2023protein]`
- Natural citations: `(Smith 2023)` or `(Smith et al. 2023)`
- LaTeX citations: `\citep{paper_id}` or `\cite{author2023}`

### Example Good Citations

```
✓ "AlphaFold2 achieved unprecedented accuracy [jumper2021alphafold]."
✓ "Deep learning approaches show promise [senior2020protein, evans2021fold]."
✓ "Transformer architectures excel in NLP tasks (Vaswani et al. 2017)."
```

### Example Poor Citations

```
✗ "Machine learning is transforming biology." (no citation)
✗ "Recent studies show improvement." (vague, no specific citation)
✗ "The method works well [nonexistent2023]." (invalid citation)
```

## Logging and Analytics

### Log Files

The system creates three log files in `logs/citations/`:

1. **`citation_failures.jsonl`** - Failed verification attempts
2. **`citation_successes.jsonl`** - Successful verifications
3. **`citation_retries.jsonl`** - Retry attempts and outcomes

### Log Entry Format

Each log entry includes:

```json
{
  "timestamp": "2023-XX-XXTXX:XX:XXZ",
  "sentence_text": "Original sentence requiring citation",
  "claim_type": "empirical_claim",
  "claim_confidence": 0.8,
  "existing_citations": ["existing_citation_keys"],
  "keywords": ["extracted", "keywords"],
  "verification_result": {
    "is_supported": false,
    "confidence": 0.2,
    "reason": "Human-readable explanation"
  },
  "context": {
    "agent_name": "generation",
    "hypothesis_id": "hyp_123",
    "iteration": 1
  }
}
```

### Analytics

Use the CLI to analyze citation patterns:

```bash
# Show failure statistics
darwin-citations stats --days 30

# Example output:
# Total failures: 25
# Failures by type:
#   empirical_claim: 15
#   statistical_claim: 8
#   factual_assertion: 2
# Common failure reasons:
#   "No supporting literature found": 12
#   "Available references not cited": 8
```

## Integration Points

### Generation Agent Enhancement

The system can enhance generation prompts to encourage proper citations:

```python
from darwin.citation_prompts import CitationPromptEnhancer

enhancer = CitationPromptEnhancer()
enhanced_prompt = enhancer.enhance_generation_prompt(
    base_prompt=original_prompt,
    literature_context=available_papers,
    enforce_citations=True
)
```

### Reflection Agent Integration

Citation quality becomes part of hypothesis scoring:

```python
# Original score: 0.8
# Citation score: 0.4 (poor citations)
# Combined score: 0.8 * 0.8 + 0.4 * 0.2 = 0.72
```

### Meta-Review Enhancement

The meta-review includes citation quality analysis:

```
CITATION QUALITY ANALYSIS:
- Average citation score: 0.65/1.0
- Well-cited hypotheses: 3/5
- Hypotheses needing citation improvement: 2

Citation recommendations:
- MODERATE: Some hypotheses need better citation support
- Consider adding more specific references to claims
```

## Configuration Options

### Environment Variables

- `DARWIN_ENFORCE_CITATIONS`: Enable strict enforcement (true/false)
- `DARWIN_ASSESS_CITATIONS`: Include citation quality in scoring (true/false)
- `DARWIN_CITATION_LOGGING`: Enable failure logging (true/false)

### Thresholds

Configurable thresholds in the system:

- **Similarity threshold**: 0.4 (minimum similarity for paper relevance)
- **Claim confidence**: 0.3 (minimum confidence to require citation)
- **Citation weight**: 0.2 (weight of citations in overall scoring)

## Testing

### Running Tests

```bash
# Full test suite
python -m pytest tests/test_citation_system.py

# Smoke tests only
darwin-citations test --smoke-test

# Individual test classes
python -m pytest tests/test_citation_system.py::TestCitationParser
```

### Test Coverage

The test suite covers:

- Sentence parsing and claim identification
- Citation extraction and verification
- Logging functionality and statistics
- Pipeline integration and report generation
- Error handling and edge cases

## Performance Considerations

### Efficiency

- Citation parsing uses compiled regex patterns for speed
- Literature keyword extraction is cached per paper
- Verification results can be cached to avoid re-computation

### Scalability

- Append-only logging is thread-safe for concurrent agents
- Log files can be rotated or archived as needed
- Statistics generation scales with log file size

### Memory Usage

- Parser and verifier instances can be reused across hypotheses
- Literature context is processed once per research session
- Log entries are streamed to avoid memory accumulation

## Troubleshooting

### Common Issues

1. **No citations detected**: Check if text contains claim indicators
2. **All citations fail verification**: Verify literature context format
3. **Log files not created**: Check directory permissions and logging configuration
4. **Poor relevance scores**: Review keyword extraction and similarity algorithms

### Debug Mode

Enable detailed logging with environment variables:

```bash
export DARWIN_DEBUG_CITATIONS=true
```

This provides verbose output for troubleshooting verification logic.

## Future Enhancements

### Planned Features

1. **Semantic similarity**: Use embeddings for better claim-paper matching
2. **Citation style templates**: Support multiple academic citation formats
3. **Reference resolution**: Automatically resolve DOIs and URLs
4. **Interactive citation suggestions**: Real-time citation assistance during generation
5. **Cross-reference validation**: Verify citations against external databases

### Integration Opportunities

1. **Literature search integration**: Automatically fetch relevant papers
2. **Version control**: Track citation changes across hypothesis iterations
3. **Collaborative filtering**: Learn from citation patterns across agents
4. **Quality metrics**: Develop more sophisticated citation quality measures