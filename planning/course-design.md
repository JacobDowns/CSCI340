# Course design rationale

## Working identity

**Database Systems and Data Management** teaches students to think with data systems. It is neither a database-administration survey nor a web-application course. Scientific and geospatial data are the instructor's home territory, but the course rotates through transactional and organizational cases whenever those cases better expose a database concept.

## Balance

- Approximately 65% core relational and database-system concepts, including an extended ER-modeling sequence
- Approximately 10% contemporary analytical systems and DataFrame comparisons
- Approximately 15% spatial data and PostGIS
- Approximately 10% integration, broader architectures, review, and design defense

These are emphases rather than isolated blocks.

## Design commitments

1. PostgreSQL is the primary relational system.
2. PostGIS is a signature application of types, indexes, functions, joins, optimization, and data representation.
3. DuckDB, Parquet, and Polars form one coherent analytical comparison rather than a survey of tools.
4. Transactional cases remain in the course because scientific data alone does not naturally motivate every concurrency or integrity problem.
5. Students repeatedly predict, test, interpret, and revise.
6. "Justify your choice" is assessed alongside correctness.
7. The capstone evolves across the semester instead of appearing as an unrelated final project.

## Recurring prompts

- Which rule belongs in the database, the transaction, or application logic?
- Which index would help this workload, and what evidence would confirm the claim?
- Should this computation occur in PostgreSQL, DuckDB, Polars, or application code?
- What information is lost or duplicated by this representation?
- Which requirement would cause us to choose a different kind of database?
- What could go wrong because of missingness, linkage, geographic boundaries, or access?
