"""
Implementation of the SexpEnvironment based on the IDL specification.
Provides a lexical scoping environment for S-expression evaluation.
"""

import logging # Ensure imported
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__) # Add logger

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
        # --- START FIX ---
        # Store a COPY of the bindings dictionary to prevent potential
        # issues with external modifications if the original dict reference was stored.
        self._bindings: Dict[str, Any] = bindings.copy() if bindings is not None else {}
        # --- END FIX ---
        self._parent: Optional['SexpEnvironment'] = parent
        # Keep the logging
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
        logger.debug(f"Lookup: Searching for '{name}' in env id={id(self)}") # Log entry
        logger.debug(f"  Local bindings in env id={id(self)}: {list(self._bindings.keys())}") # Log local keys

        if name in self._bindings:
            value = self._bindings[name]
            logger.debug(f"  Found '{name}' in local bindings of env id={id(self)}. Value type: {type(value)}")
            return value
        elif self._parent is not None:
            parent_id = id(self._parent)
            logger.debug(f"  '{name}' not found locally, checking parent env id={parent_id}")
            try:
                # Recursively lookup in parent
                return self._parent.lookup(name) # Let parent raise NameError if not found
            except NameError:
                 # Log that the parent lookup failed before raising
                logger.debug(f"  '{name}' not found in parent chain starting from env id={parent_id}.")
                raise # Re-raise the NameError from the parent lookup
        else:
            logger.debug(f"  '{name}' not found locally and no parent for env id={id(self)}.")
            # Reached top-level scope without finding the name
            raise NameError(f"Unbound symbol: Name '{name}' is not defined.") # Use NameError as before

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

    def set_value_in_scope(self, name: str, value: Any) -> None:
        """Sets the value of an *existing* variable in the current or an ancestor scope.

        Searches for the variable 'name' starting from the current environment
        and going up the parent chain. The first binding found is updated.

        Args:
            name: The name (symbol string) of the variable to update.
            value: The new value for the variable.

        Raises:
            NameError: If the name is not found in this environment or any
                       of its ancestor environments (i.e., cannot set unbound variable).
        """
        logging.debug(f"Attempting to set '{name}' = (type: {type(value).__name__}, value: {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}) in env chain starting from {id(self)}")
        env: Optional[SexpEnvironment] = self
        while env is not None:
            if name in env._bindings:
                logging.debug(f"Found '{name}' in env {id(env)}, updating value.")
                env._bindings[name] = value
                return
            logging.debug(f"'{name}' not in local bindings of env {id(env)}, checking parent ({id(env._parent) if env._parent else 'None'}).")
            env = env._parent
        
        # If loop completes, name was not found in any scope
        logging.error(f"Cannot 'set!' unbound symbol: Name '{name}' is not defined in any accessible scope.")
        raise NameError(f"Unbound symbol: Cannot set! '{name}' as it's not defined.")

    # --- Optional helper methods for debugging or inspection ---

    def get_local_bindings(self) -> Dict[str, Any]:
        """Returns a copy of the bindings defined directly in this scope."""
        return self._bindings.copy()

    def __repr__(self) -> str:
        parent_id = id(self._parent) if self._parent else None
        return f"<SexpEnvironment id={id(self)} parent={parent_id} bindings={list(self._bindings.keys())}>"
