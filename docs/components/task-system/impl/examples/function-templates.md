# Function Invocation via S-Expression DSL (Formerly Function Templates)

**Status: Obsolete**

This document previously described function-style templates defined using XML `<template>` and `<call>` elements.

In the current architecture:
*   Reusable tasks are defined as **atomic tasks** in XML using `<task type="atomic" name="...">`.
*   All task invocation and workflow composition (including calling named atomic tasks) is handled via the **S-expression DSL**.

Please refer to the S-expression DSL documentation [Link TBD] and examples showing how to call named atomic tasks using the `(<task_name> (arg_name arg_value) ...)` syntax within S-expressions.
