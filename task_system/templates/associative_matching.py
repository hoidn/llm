"""Associative matching template for finding relevant files."""
from typing import Dict, List, Any, Tuple
import re
import os
import math

# Template definition as a Python dictionary to be converted to XML
ASSOCIATIVE_MATCHING_TEMPLATE = {
    "type": "atomic",
    "subtype": "associative_matching",
    "description": "Find relevant files for the given query",
    "inputs": {
        "query": "The user query or task to find relevant files for"
    },
    "context_management": {
        "inherit_context": "none",
        "accumulate_data": False,
        "fresh_context": "disabled"
    },
    "output_format": {
        "type": "json",
        "schema": "string[]"
    }
}

def register_template(task_system) -> None:
    """Register the associative matching template with the Task System.
    
    Args:
        task_system: The Task System instance
    """
    task_system.register_template(ASSOCIATIVE_MATCHING_TEMPLATE)

def create_xml_template() -> str:
    """Create the XML representation of the template.
    
    Returns:
        XML string representing the template
    """
    # This is a helper to generate the actual XML when needed
    xml = """
    <task type="atomic" subtype="associative_matching">
      <description>Find relevant files for the given query</description>
      <inputs>
        <input name="query">The user query or task to find relevant files for</input>
      </inputs>
      <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>false</accumulate_data>
        <fresh_context>disabled</fresh_context>
      </context_management>
      <output_format type="json" schema="string[]" />
    </task>
    """
    return xml

def execute_template(query: str, memory_system) -> List[str]:
    """Execute the associative matching template logic.
    
    This function implements the actual template execution logic when invoked
    by the task system. It finds files relevant to the given query using
    a simple scoring algorithm.
    
    Args:
        query: The user query or task
        memory_system: The Memory System instance
        
    Returns:
        List of relevant file paths, sorted by relevance
    """
    # Normalize query
    query_terms = normalize_text(query)
    
    # Get global index from memory system
    file_metadata = get_global_index(memory_system)
    if not file_metadata:
        print("No indexed files found. Run index_git_repository first.")
        return []
    
    # Score files
    scored_files = score_files(file_metadata, query_terms)
    
    # Get top 10 most relevant files
    top_files = [path for path, score in scored_files[:10]]
    
    return top_files

def normalize_text(text: str) -> List[str]:
    """Normalize text for scoring.
    
    Args:
        text: Text to normalize
        
    Returns:
        List of normalized terms
    """
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation and split into words
    words = re.findall(r'\w+', text)
    
    # Remove common stop words (simplified list)
    stop_words = {
        'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
        'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'of'
    }
    
    # Filter out stop words and words less than 3 characters
    filtered_words = [word for word in words if word not in stop_words and len(word) >= 3]
    
    return filtered_words

def score_files(file_metadata: Dict[str, str], query_terms: List[str]) -> List[Tuple[str, float]]:
    """Score files based on relevance to query terms.
    
    Args:
        file_metadata: Dictionary mapping file paths to metadata
        query_terms: List of normalized query terms
        
    Returns:
        List of (file_path, score) tuples, sorted by score descending
    """
    scores = []
    
    # Extract IDF (inverse document frequency) for each term
    term_doc_count = {}
    for term in query_terms:
        term_doc_count[term] = 0
    
    # Count documents containing each term
    for path, metadata in file_metadata.items():
        metadata_terms = normalize_text(metadata)
        for term in query_terms:
            if term in metadata_terms:
                term_doc_count[term] += 1
    
    # Calculate IDF for each term
    num_docs = len(file_metadata)
    term_idf = {}
    for term, count in term_doc_count.items():
        # Add 1 to avoid division by zero
        term_idf[term] = math.log((num_docs + 1) / (count + 1)) + 1
    
    # Score each file
    for path, metadata in file_metadata.items():
        metadata_terms = normalize_text(metadata)
        
        # Calculate term frequency
        term_freq = {}
        for term in metadata_terms:
            term_freq[term] = term_freq.get(term, 0) + 1
        
        # Calculate TF-IDF score
        score = 0
        for term in query_terms:
            # Term frequency in this document
            tf = term_freq.get(term, 0)
            # Get IDF value
            idf = term_idf.get(term, 1)
            # Add to score
            score += tf * idf
        
        # Boost score for matches in file name or path
        file_name = os.path.basename(path).lower()
        for term in query_terms:
            if term in file_name:
                score *= 1.5  # 50% boost for terms in filename
        
        # Add to scores if non-zero
        if score > 0:
            scores.append((path, score))
    
    # Sort by score descending
    return sorted(scores, key=lambda x: x[1], reverse=True)

def get_global_index(memory_system) -> Dict[str, str]:
    """Get the global index from the memory system.
    
    This function provides compatibility with different Memory System implementations.
    
    Args:
        memory_system: The Memory System instance
        
    Returns:
        Dictionary mapping file paths to metadata
    """
    # Try different methods to get the global index
    if hasattr(memory_system, 'get_global_index'):
        return memory_system.get_global_index()
    elif hasattr(memory_system, 'global_index'):
        return memory_system.global_index
    else:
        # Return empty dict if global index not found
        return {}
