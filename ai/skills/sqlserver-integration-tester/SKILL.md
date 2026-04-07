---
name: sqlserver-integration-tester
description: "Expert SQL Server integration test agent using testcontainers-go. Use this whenever writing integration tests that need a real SQL Server database, testing GORM data access layers, or validating schema-dependent behavior that mocked databases miss (like NOT NULL constraints, datetime handling, batch inserts)."
version: "1.0.0"
triggers:
  - "sqlserver integration test"
  - "testcontainer test"
  - "real database test"
  - "data access integration test"
---

# SQL Server Integration Tester

Expert agent for writing comprehensive integration tests against SQL Server using testcontainers-go.
Catches bugs that mocked/SQLite databases miss: type mismatches, NOT NULL violations, batch INSERT
behavior, GORM naming strategy issues, and stored procedure compatibility.

## When to Use

- Writing or reviewing data access code in `pkg/repo/`
- After finding a bug that unit tests with mocks didn't catch
- Validating GORM model ↔ SQL Server schema compatibility
- Testing batch operations, transactions, or concurrent data access
- Any PR that modifies `config/sqlserver.go` or GORM configuration

## Context

This project uses:
- **GORM v1.26.0** with **gorm.io/driver/sqlserver v1.5.4**
- **Custom MSSQLNamingStrategy** (PascalCase, NoLowerCase=true) at `config/sqlserver.go`
- **Existing integration test infra** at `pkg/testing/integration/` — uses external SQL Server via `TEST_DB_DSN` env var
- **Build tag:** `//go:build integration` — tests only run with `-tags integration`
- **Test guide:** `docs/guides/go-unit-testing-agent-guide.md`

## Instructions

### Step 1 — Understand the Test Target

Read the file(s) being tested. Identify:
- Which GORM operations are used (Create, Find, Updates, Raw, Exec)
- Whether batch operations are involved (slice of structs or maps)
- Which model structs map to which tables
- Any NOT NULL columns, defaults, or constraints

### Step 2 — Check Existing Coverage

```
Grep for existing integration tests: *_integration_test.go
Check pkg/testing/integration/ for available helpers
```

### Step 3 — Write the Test

Follow these conventions:

```go
//go:build integration

package repo_test

import (
    "context"
    "testing"
    
    "axosclearing.com/AxosUniversalCore/auc-conversion/pkg/testing/integration"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestIntegration_<Component>_<Behavior>_<ExpectedResult>(t *testing.T) {
    t.Parallel()
    
    // Use RequireDBWithCleanup for tests that INSERT data
    db := integration.RequireDBWithCleanup(t, "config.TableName")
    integration.RunMigrations(t, db)
    ctx := context.Background()
    
    // Use factory builders for test data
    entity := integration.NewProcessLog().Processing().Build()
    require.NoError(t, db.Create(&entity).Error)
    
    // Test the actual repository method
    repo := NewRepository(db)
    result, err := repo.Method(ctx, args)
    
    // Assert with descriptive messages explaining WHY
    require.NoError(t, err, "Method should succeed because <reason>")
    assert.Equal(t, expected, result.Field,
        "Field should be X because <business reason>")
}
```

### Step 4 — Critical Patterns to Test

**ALWAYS test these for any GORM data access:**

1. **NOT NULL columns with GORM batch Create:**
   ```go
   // Verify all NOT NULL columns are populated after batch insert
   var persisted []Model
   db.Where("ParentID = ?", id).Find(&persisted)
   for i, r := range persisted {
       assert.False(t, r.CreatedAt.IsZero(), "row[%d] CreatedAt must not be zero", i)
   }
   ```

2. **PascalCase column name preservation:**
   ```go
   // Verify GORM generates correct column names for SQL Server
   // This catches MSSQLNamingStrategy bugs
   ```

3. **Map vs Struct Create behavior:**
   ```go
   // GORM SQL Server driver drops columns from map-based batch inserts
   // Always test that struct-based Create includes all columns
   ```

4. **Transaction rollback on error:**
   ```go
   // Inject error mid-transaction, verify rollback
   ```

5. **Concurrent access (ROWLOCK/READPAST):**
   ```go
   // Use integration.RunConcurrently() for parallel claim tests
   ```

### Step 5 — Testcontainers Setup (Future)

When testcontainers-go is added to the project:

```go
package integration

import (
    "context"
    "fmt"
    "testing"
    
    "github.com/testcontainers/testcontainers-go"
    "github.com/testcontainers/testcontainers-go/modules/mssql"
)

func RequireTestcontainerDB(t testing.TB) *gorm.DB {
    t.Helper()
    ctx := context.Background()
    
    container, err := mssql.Run(ctx,
        "mcr.microsoft.com/mssql/server:2022-latest",
        mssql.WithAcceptEULA(),
        mssql.WithPassword("YourStrong@Passw0rd"),
    )
    require.NoError(t, err)
    t.Cleanup(func() { container.Terminate(ctx) })
    
    dsn, err := container.ConnectionString(ctx)
    require.NoError(t, err)
    
    db, err := gorm.Open(sqlserver.Open(dsn), &gorm.Config{
        NamingStrategy: config.MSSQLNamingStrategy{
            NamingStrategy: schema.NamingStrategy{NoLowerCase: true},
        },
    })
    require.NoError(t, err)
    
    // Run schema migrations
    RunMigrations(t, db)
    
    return db
}
```

### Step 6 — Known GORM + SQL Server Gotchas

| Issue | What Happens | How to Catch |
|-------|-------------|-------------|
| Map batch Create drops columns | NULL for NOT NULL fields | Integration test with NOT NULL assertion |
| NamingStrategy missing ColumnName() | Column name mismatch | Test PascalCase column round-trip |
| autoCreateTime with explicit value | May be ignored in batch | Test CreatedAt != zero after Create |
| OUTPUT INSERTED vs RETURNING | Different SQL for batch | Mock expects Query not Exec |
| String datetime in map | NULL on SQL Server | Fitness test + integration test |

## Related Skills

- `/hawk` — code review that flags GORM anti-patterns
- `/test-author` — general Go test writing agent
