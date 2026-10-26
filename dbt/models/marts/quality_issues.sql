select * from {{ source('ingestion', 'dq_current') }}
