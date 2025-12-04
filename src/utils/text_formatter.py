import re
from nonebot.log import logger

def markdown_to_plain_text(text):
    """
    Convert Markdown formatted text to QQ-friendly plain text.
    Handles common Markdown syntax like bold, italic, headers, lists, code blocks, etc.
    """
    if not text:
        return text
    
    try:
        result = text
        
        # Remove code blocks (```code```) - replace with indented text
        result = re.sub(r'```[\w]*\n(.*?)\n```', r'\1', result, flags=re.DOTALL)
        
        # Remove inline code backticks (`code`) - keep the content
        result = re.sub(r'`([^`]+)`', r'\1', result)
        
        # Headers (# Header) -> just the text with emphasis
        result = re.sub(r'^#{1,6}\s+(.+)$', r'【\1】', result, flags=re.MULTILINE)
        
        # Bold (**text** or __text__) -> keep text
        result = re.sub(r'\*\*([^\*]+)\*\*', r'\1', result)
        result = re.sub(r'__([^_]+)__', r'\1', result)
        
        # Italic (*text* or _text_) -> keep text
        result = re.sub(r'\*([^\*]+)\*', r'\1', result)
        result = re.sub(r'_([^_]+)_', r'\1', result)
        
        # Links [text](url) -> text (url)
        result = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'\1 (\2)', result)
        
        # Unordered lists (- item or * item) -> keep structure with Chinese bullet
        result = re.sub(r'^\s*[-\*]\s+', '• ', result, flags=re.MULTILINE)
        
        # Ordered lists (1. item) -> keep numbered
        # Already looks fine in plain text
        
        # Horizontal rules (--- or ***) -> use text separator
        result = re.sub(r'^[\-\*]{3,}$', '━━━━━━━━━━━━━━━━', result, flags=re.MULTILINE)
        
        # Blockquotes (> text) -> keep with quote marker
        result = re.sub(r'^>\s+', '> ', result, flags=re.MULTILINE)
        
        # Clean up extra blank lines (more than 2 consecutive)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()
        
    except Exception as e:
        # If conversion fails, log error and return original text
        logger.warning(f"Failed to convert markdown to plain text: {e}")
        return text
