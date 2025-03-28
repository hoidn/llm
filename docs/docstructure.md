# Documentation Structure

## Directory Layout
```
docs/
├── system/                         # System-level documentation
│   ├── README.md                   # System overview & development sequence
│   ├── docs-guide.md               # Documentation standards, map & navigation
│   ├── architecture/               # Core architecture
│   │   ├── overview.md            # High-level design
│   │   ├── decisions/             # Architecture Decision Records (ADRs)
│   │   └── patterns/              # Core patterns & principles
│   ├── protocols/                  # System-wide protocols
│   │   └── resources.md            # Protocol-level resource definitions
│   └── contracts/                  # System-wide contracts
│       ├── interfaces.md          # External interfaces
│       └── resources.md           # Resource management
│
└── components/                     # Component documentation
    └── [component]/               # Per component (can be nested)
        ├── README.md              # Component overview
        ├── api/                   # Public API documentation
        │   └── interfaces.md      # Public interface definitions
        ├── spec/                  # Formal specifications
        │   ├── requirements.md    # Component requirements
        │   ├── interfaces.md      # Internal interface definitions
        │   ├── types.md          # Type definitions
        │   └── behaviors.md       # Expected behaviors
        └── impl/                  # Implementation details
            ├── design.md         # Design decisions
            ├── protocols.md      # Protocol implementations
            └── examples.md       # Implementation examples
```

## Common Types
[Rest of common types section remains unchanged]

## Cross-Reference Updates
Ensure that all components referencing the Director-Evaluator pattern mention both the dynamic and static variants. In particular, update references to [Pattern:DirectorEvaluator:1.1] to include the static variant with script execution support.

## Document Standards

### System Level Documents

#### README.md
[README.md template remains unchanged]

#### docs-guide.md
```markdown
# Documentation Guide

## Documentation Map
Required:
- Core system specifications
- Component contracts & integration
- Core patterns & protocols
- Key data structures
- Documentation status
- Cross-reference guide

## Standards
Required:
- Writing style guidelines
- Document templates
- Cross-reference syntax
- Version control practices

## Documentation Principles
Required:
1. Single Responsibility
   - Each document covers one concern
   - Clear boundaries between concerns
   - Explicit dependencies
2. Template Consistency
   - All new task templates must use the unified template substitution mechanism.
   - Evaluator's lexically scoped variables are referenced using the `{{variable_name}}` syntax.
   - Input bindings can be explicitly declared using the optional `from` attribute on `<input>` elements.

2. Contract Completeness
   - All requirements stated
   - All guarantees explicit
   - All resources documented

3. Resource Clarity
   - Ownership explicit
   - Lifecycle documented
   - Cleanup requirements specified

## Writing Style
Required:
1. Active voice
2. One sentence per line
3. Explicit section numbering
4. Consistent terminology

## Documentation Map
Required:
- Core system specifications
- Component contracts & integration
- Core patterns & protocols
- Key data structures
- Documentation status

## Version Management
Required:
1. Version Format: MAJOR.MINOR.PATCH
2. Update Rules:
   - MAJOR: Breaking changes
   - MINOR: New features, backward compatible
   - PATCH: Bug fixes, backward compatible

## Navigation
Required:
1. Documentation Map Usage
   - Primary navigation aid
   - Definitive specification locations
   - Cross-reference resolution
   - Documentation status tracking

2. Map Maintenance
   - Regular updates with changes
   - Validation of references
   - Status accuracy verification
   - Gap identification

Note: The Documentation Map in this guide serves as the primary navigation aid
for finding specifications and understanding document relationships.

## Templates
[See individual document templates in this guide]
```

[Rest of document remains unchanged]
