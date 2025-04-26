"""
Implementation of the SexpEnvironment based on the IDL specification.
Provides a lexical scoping environment for S-expression evaluation.
"""

from typing import Any, Dict, Optional, Union

class SexpEnvironment:
    """
    Represents a lexical environment for S-expression evaluation,
    supporting variable lookup, definition, and nested scopes.

    Implements the contract defined in src/sexp_evaluator/sexp_environment_IDL.md.
    """

    def __init__(self, parent: Optional['SexpEnvironment'] = None):
        """
        Initializes a new SexpEnvironment.

        Args:
            parent: An optional parent environment for creating nested scopes.
                    Defaults to None, indicating a top-level scope.
        """
        self._bindings: Dict[str, Any] = {}
        self._parent: Optional['SexpEnvironment'] = parent

    def lookup(self, name: str) -> Any:
        """
        Looks up a variable name in the environment and its parent scopes.

        Args:
            name: The name of the variable to look up.

        Returns:
            The value associated with the name.

        Raises:
            NameError: If the name is not found in this environment or any
                       of its ancestor environments.
        """
        if name in self._bindings:
            return self._bindings[name]
        elif self._parent is not None:
            try:
                return self._parent.lookup(name)
            except NameError:
                # Catch NameError from parent and raise a new one with the original name
                raise NameError(f"Name '{name}' is not defined in the environment chain.")
        else:
            raise NameError(f"Name '{name}' is not defined.")

    def define(self, name: str, value: Any) -> None:
        """
        Defines or redefines a variable in the current environment scope.

        Args:
            name: The name of the variable to define.
            value: The value to associate with the name.
        """
        # IDL doesn't specify behavior for redefining, standard practice is to allow it.
        self._bindings[name] = value

    def extend(self, bindings: Dict[str, Any]) -> 'SexpEnvironment':
        """
        Creates a new child environment with additional bindings, inheriting
        from the current environment.

        Args:
            bindings: A dictionary of new variable names and their values
                      to add to the child environment.

        Returns:
            A new SexpEnvironment instance that has the current environment
            as its parent and includes the new bindings.
        """
        child_env = SexpEnvironment(parent=self)
        child_env._bindings.update(bindings) # Add new bindings to the child
        return child_env

    # Optional helper for debugging or inspection
    def get_local_bindings(self) -> Dict[str, Any]:
        """Returns a copy of the bindings defined directly in this scope."""
        return self._bindings.copy()
