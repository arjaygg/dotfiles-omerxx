91 lines → 70 unique
1 errors:
  - **Index foreign keys** — Always, no exceptions
last 15 unique lines:
## Review Checklist
- [ ] All WHERE/JOIN columns indexed
- [ ] Composite indexes in correct column order
- [ ] Proper data types (bigint, text, timestamptz, numeric)
- [ ] RLS enabled on multi-tenant tables
- [ ] RLS policies use `(SELECT auth.uid())` pattern
- [ ] Foreign keys have indexes
- [ ] No N+1 query patterns
- [ ] EXPLAIN ANALYZE run on complex queries
- [ ] Transactions kept short
## Reference
For detailed index patterns, schema design examples, connection management, concurrency strategies, JSONB patterns, and full-text search, see skills: `postgres-patterns` and `database-migrations`.
---
**Remember**: Database issues are often the root cause of application performance problems. Optimize queries and schema design early. Use EXPLAIN ANALYZE to verify assumptions. Always index foreign keys and RLS policy columns.
*Patterns adapted from Supabase Agent Skills (credit: Supabase team) under MIT license.*
[lean-ctx: 1031→243 tok, -76%]
