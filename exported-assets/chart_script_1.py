# Create a detailed flowchart for web crawler resource management
diagram_code = '''
flowchart TD
    A[Initialize Resources<br/>512MB RAM, 0.5 vCPU<br/>Concurrency: 10] --> B{Health Check<br/>Every 30s}
    
    B --> C{Memory < 400MB?}
    
    C -->|Yes| D{CPU < 60%?}
    C -->|No| E{Memory > 450MB?}
    
    D -->|Yes| F[Allow New Requests<br/>Monitor Queue Depth]
    D -->|No| G{CPU > 80%?}
    
    E -->|Yes| H[Emergency Mode<br/>Pause All Requests<br/>Trigger Cleanup]
    E -->|No| I[Memory Warning<br/>Reduce Concurrency<br/>Trigger GC]
    
    G -->|Yes| J[CPU Critical<br/>Add Delays<br/>Scale Down to 5]
    G -->|No| K[CPU Warning<br/>Reduce Rate<br/>Scale Down 20→15→10]
    
    F --> L{Queue Depth OK?}
    L -->|Yes| M[Scale Up<br/>10→15→20]
    L -->|No| N[Maintain Current<br/>Monitor Backlog]
    
    H --> O[Cleanup Process<br/>60s Duration<br/>Memory Recovery]
    I --> P[Garbage Collection<br/>Reduce Concurrency]
    J --> Q[Exponential Backoff<br/>Error Recovery]
    K --> R[Rate Limiting<br/>Performance Mode]
    
    O --> B
    P --> B
    Q --> B
    R --> B
    M --> B
    N --> B

    classDef memoryNode fill:#e1f5fe,stroke:#01579b,color:#000
    classDef cpuNode fill:#ffebee,stroke:#c62828,color:#000
    classDef networkNode fill:#e8f5e8,stroke:#2e7d32,color:#000
    classDef actionNode fill:#fff3e0,stroke:#ef6c00,color:#000
    
    class C,E,I,O,P memoryNode
    class D,G,J,K,Q,R cpuNode
    class F,L,M,N networkNode
    class A,B,H actionNode
'''

# Create the mermaid diagram and save as both PNG and SVG
png_path, svg_path = create_mermaid_diagram(diagram_code, "resource_management_flowchart.png", "resource_management_flowchart.svg")

print(f"Flowchart saved as: {png_path} and {svg_path}")