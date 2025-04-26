"""
System-wide custom error types.
"""

class SexpSyntaxError(ValueError):
    """
    Custom exception raised when S-expression parsing fails due to syntax errors.
    Inherits from ValueError for general compatibility but provides specific context.
    """
    def __init__(self, message: str, sexp_string: str, error_details: str = ""):
        """
        Initializes the SexpSyntaxError.

        Args:
            message: A high-level error message.
            sexp_string: The original S-expression string that caused the error.
            error_details: Specific details from the underlying parser, if available.
        """
        full_message = f"{message}\nInput: '{sexp_string}'"
        if error_details:
            full_message += f"\nDetails: {error_details}"
        super().__init__(full_message)
        self.sexp_string = sexp_string
        self.error_details = error_details
