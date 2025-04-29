"""
Implementation of the SexpEnvironment based on the IDL specification.
Provides a lexical scoping environment for S-expression evaluation.
"""

import logging
from typing import Any, Dict, Optional

class SexpEnvironment:
    """
    Represents a lexical environment for S-expression evaluation,
    supporting variable lookup, definition, and nested scopes.

    Implements the contract defined in src/sexp_evaluator/sexp_evaluator_IDL.md (SexpEnvironment interface).
    Note: This environment is distinct from the simple parameter dictionary used
    by AtomicTaskExecutor for template substitution.
    """

    def __init__(
        self,
        bindings: Optional[Dict[str, Any]] = None,
        parent: Optional['SexpEnvironment'] = None
    ):
        """
        Initializes a new SexpEnvironment.

        Args:
            bindings: An optional dictionary of initial variable bindings for this scope.
            parent: An optional parent environment for creating nested scopes.
                    Defaults to None, indicating a top-level scope.
        """
        self._bindings: Dict[str, Any] = bindings if bindings is not None else {}
        self._parent: Optional['SexpEnvironment'] = parent
        logging.debug(f"Initialized SexpEnvironment (Parent: {parent is not None}, Bindings: {list(self._bindings.keys())})")

    def lookup(self, name: str) -> Any:
        """
        Looks up a variable name in the environment and its parent scopes.

        Args:
            name: The name (symbol) of the variable to look up.

        Returns:
            The value associated with the name.

        Raises:
            NameError: If the name is not found in this environment or any
                       of its ancestor environments. This signals an unbound symbol error
                       during S-expression evaluation.
        """
        logging.debug(f"Looking up '{name}' in env {id(self)}")
        if name in self._bindings:
            logging.debug(f"Found '{name}' in local bindings.")
            return self._bindings[name]
        elif self._parent is not None:
            logging.debug(f"'{name}' not found locally, checking parent env {id(self._parent)}")
            # Recursively lookup in parent
            return self._parent.lookup(name) # Let parent raise NameError if not found
        else:
            logging.debug(f"'{name}' not found locally and no parent.")
            # Reached top-level scope without finding the name
            raise NameError(f"Unbound symbol: Name '{name}' is not defined.")

    def define(self, name: str, value: Any) -> None:
        """
        Defines or redefines a variable in the *current* environment scope.
        This does not affect parent scopes.

        Args:
            name: The name (symbol) of the variable to define.
            value: The evaluated value to associate with the name.
        """
        logging.debug(f"Defining '{name}' = {type(value)} in env {id(self)}")
        # IDL doesn't specify behavior for redefining, standard practice is to allow it.
        self._bindings[name] = value

    def extend(self, bindings: Dict[str, Any]) -> 'SexpEnvironment':
        """
        Creates a new child environment that extends the current environment.
        The new child environment will have the current environment as its parent
        and will contain the additional specified bindings in its local scope.

        Args:
            bindings: A dictionary of new variable names and their evaluated values
                      to add to the child environment's local scope.

        Returns:
            A new SexpEnvironment instance representing the child scope.
        """
        logging.debug(f"Extending env {id(self)} with bindings: {list(bindings.keys())}")
        # Create a new environment with self as parent and the new bindings
        child_env = SexpEnvironment(bindings=bindings, parent=self)
        return child_env

    # --- Optional helper methods for debugging or inspection ---

    def get_local_bindings(self) -> Dict[str, Any]:
        """Returns a copy of the bindings defined directly in this scope."""
        return self._bindings.copy()

    def __repr__(self) -> str:
        parent_id = id(self._parent) if self._parent else None
        return f"<SexpEnvironment id={id(self)} parent={parent_id} bindings={list(self._bindings.keys())}>"
