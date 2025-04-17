**Status: Superseded**

**This plan proposed implementing Director/Evaluator functionality as subtypes of atomic tasks. The final architecture implemented this pattern using a distinct composite task type `director_evaluator_loop`, which is executed by the `Evaluator` component. Please refer to the canonical [Director-Evaluator Pattern documentation](../system/architecture/patterns/director-evaluator.md) for the current design.**

1. Type Hierarchy Recommendation

mermaid
Copy
graph TD
    Task[Base Task Type]
    Task --> Atomic
    Task --> Sequential
    Task --> Reduce
    Atomic --> Director
    Atomic --> Evaluator
    classDef atomic fill:#cff,stroke:#099;
    class Director,Evaluator atomic
2. XML Implementation Strategy

xml
Copy
<!-- As atomic subtypes -->
<task type="atomic" subtype="director">
    <continuation_policy>latest-only</continuation_policy>
    <output_slot>last_eval_input</output_slot>
</task>

<task type="atomic" subtype="evaluator">
    <input_source>last_eval_input</input_source>
    <validation_rules>strict</validation_rules>
</task>

<!-- Example using template substitution for input binding -->
<task type="atomic">
    <description>Process {{input_data}} with parameters from {{config}}</description>
    <inputs>
        <input name="data" from="input_data"/>
        <input name="settings" from="config"/>
    </inputs>
</task>
Run HTML
3. Advantages of Atomic Subtyping

Aspect	Benefit
Execution Flow	Inherits standard atomic task lifecycle (init → execute → cleanup)
Error Handling	Uses existing atomic error recovery patterns
Resource Tracking	Leverages atomic task's turn counting & context management
Template Matching	Works with current associative matching system
4. Context Management Additions

typescript
Copy
interface AtomicTaskEnv {
    // Shared atomic properties
    turnsUsed: number;
    contextWindowUsage: number;
    
    // Director-Evaluator specific
    lastEvaluation?: {
        output: string;
        timestamp: Date;
        success: boolean;
    };
}
5. Implementation Requirements

a. Subtype Registration

typescript
Copy
// In task-system initialization
registerAtomicSubtype('director', {
    continuationHandler: handleDirectorContinuation,
    maxTurns: 10 // Special limit for directors
});

registerAtomicSubtype('evaluator', {
    outputValidation: strictJSONValidator,
    autoClearContext: true
});
b. Execution Flow Modifications

Copy
[Director Task]
1. Execute as normal atomic task
2. On CONTINUATION:
   a. Store output in lastEvaluation slot
   b. Clear other context variables
   c. Pass control to Evaluator subtype

[Evaluator Task]
1. Receive lastEvaluation data as input
2. Execute validation/processing
3. Return results to parent environment
4. Auto-clear lastEvaluation slot
6. XML Schema Changes (operators.md update)

diff
Copy
<xs:element name="task">
  <xs:complexType>
    <xs:attribute name="type" use="required">
      <xs:simpleType>
        <xs:restriction base="xs:string">
          <xs:enumeration value="atomic"/>
          <xs:enumeration value="sequential"/>
          <xs:enumeration value="reduce"/>
+         <xs:enumeration value="script"/>
        </xs:restriction>
      </xs:simpleType>
    </xs:attribute>
+   <xs:attribute name="subtype">
+     <xs:simpleType>
+       <xs:restriction base="xs:string">
+         <xs:enumeration value="director"/>
+         <xs:enumeration value="evaluator"/>
+       </xs:restriction>
+     </xs:simpleType>
+   </xs:attribute>
  </xs:complexType>
</xs:element>
7. Transition Plan

Phase 1: Add subtype support to atomic tasks

Phase 2: Migrate existing director/evaluator templates

Phase 3: Deprecate top-level director/evaluator types

Phase 4: Update documentation (errorspec.md, operators.md)

## Implementation Implications

The atomic subtyping approach provides precise technical advantages:

- **Execution Model Integration**: Subtypes inherit the established turn tracking, resource management, and cleanup protocols already defined for atomic tasks
- **Architecture Simplification**: Reduces duplicated code by keeping atomic behavior in a single class hierarchy rather than implementing separate task types
- **Integration Cost Reduction**: Requires only minimal changes to the XML schema (adding the `subtype` attribute) rather than introducing new top-level element types
- **Template System Compatibility**: Existing template matching logic continues to work without modification

This approach balances specialization needs with architectural consistency, while maintaining the simplified context model from previous planning.
