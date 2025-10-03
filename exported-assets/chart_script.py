# Create a more compact and readable architecture diagram for the web crawler system
diagram_code = """
flowchart TB
    %% Configuration Layer (Top)
    subgraph ConfigLayer ["🔧 CONFIGURATION LAYER"]
        Config["YAML/ENV<br/>Configuration"]
        RobotsCache["Robots.txt<br/>Cache"]
    end

    %% Core Crawler Layer with prominent resource constraints
    subgraph CoreCrawler ["⚙️ CORE CRAWLER LAYER<br/>🚨 0.5 vCPU | 512MB RAM | 10-20 Requests"]
        EventLoop["Asyncio<br/>Event Loop"]
        Semaphore["Bounded<br/>Semaphore"]
        SessionPool["HTTP Session<br/>Pool"]
    end

    %% Queue Management Layer
    subgraph QueueMgmt ["📋 QUEUE MANAGEMENT"]
        RedisQueue["Redis Frontier<br/>Queue"]
        URLFilter["URL Filter<br/>(In-Memory)"]
        DomainScheduler["Domain<br/>Scheduler"]
    end

    %% External Services (side by side)
    subgraph External ["🌐 EXTERNAL SERVICES"]
        Redis[("Redis<br/>Queue Backend")]
        TargetSites[("Music Sites<br/>Target Websites")]
    end

    %% Storage and Output (bottom row)
    subgraph DataLayer ["💾 DATA LAYER"]
        PostgreSQL["PostgreSQL<br/>Results & Metadata"]
    end
    
    subgraph OutputLayer ["📤 OUTPUT LAYER"]
        CSV["CSV Export"]
        JSON["JSON Export"]
        Logs["System Logs"]
    end

    %% Main Data Flow (thick blue arrows)
    Config ==>|"Settings"| EventLoop
    Redis ==>|"URLs"| RedisQueue
    RedisQueue ==>|"Queue"| URLFilter
    URLFilter ==>|"Filtered"| DomainScheduler
    DomainScheduler ==>|"Schedule"| Semaphore
    EventLoop ==>|"Control"| SessionPool
    Semaphore ==>|"Limit"| SessionPool
    SessionPool ==>|"Request"| TargetSites
    TargetSites ==>|"Content"| PostgreSQL
    PostgreSQL ==>|"Export"| CSV
    PostgreSQL ==>|"Export"| JSON
    PostgreSQL ==>|"Logs"| Logs

    %% Error Handling & Control Flow (dashed red arrows)
    RobotsCache -.->|"Permission<br/>Check"| SessionPool
    SessionPool -.->|"Errors &<br/>Backoff"| DomainScheduler
    DomainScheduler -.->|"Retry"| RedisQueue
    TargetSites -.->|"Rate Limit<br/>Response"| Semaphore

    %% Layer Styling with distinct colors
    classDef configStyle fill:#b3e5ec,stroke:#1fb8cd,stroke-width:4px,color:#000
    classDef crawlerStyle fill:#ffeb8a,stroke:#d2ba4c,stroke-width:4px,color:#000
    classDef queueStyle fill:#a5d6a7,stroke:#2e8b57,stroke-width:4px,color:#000
    classDef externalStyle fill:#ffcdd2,stroke:#db4545,stroke-width:4px,color:#000
    classDef dataStyle fill:#9fa8b0,stroke:#5d878f,stroke-width:4px,color:#000
    classDef outputStyle fill:#e1bee7,stroke:#944454,stroke-width:4px,color:#000

    class ConfigLayer configStyle
    class CoreCrawler crawlerStyle
    class QueueMgmt queueStyle
    class External externalStyle
    class DataLayer dataStyle
    class OutputLayer outputStyle

    %% Individual component styling for better readability
    classDef componentStyle fill:#ffffff,stroke:#333,stroke-width:2px,color:#000
    class Config,RobotsCache,EventLoop,Semaphore,SessionPool,RedisQueue,URLFilter,DomainScheduler,Redis,TargetSites,PostgreSQL,CSV,JSON,Logs componentStyle
"""

# Create the more compact and readable diagram
png_path, svg_path = create_mermaid_diagram(
    diagram_code, 
    "compact_crawler_architecture.png",
    "compact_crawler_architecture.svg",
    width=1200,
    height=1400
)

print(f"Compact architecture diagram saved as: {png_path} and {svg_path}")