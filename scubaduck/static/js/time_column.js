// Helper for choosing a default time column based on column names/types
function guessTimeColumn(columns) {
  const heur = ['timestamp','created','created_at','event_time','time','date','occurred','happened','logged'];
  let guess = null;
  let first = null;
  columns.forEach(c => {
    const t = (c.type || '').toUpperCase();
    const isNumeric = t.includes('INT') || t.includes('DECIMAL') || t.includes('NUMERIC') ||
                      t.includes('REAL') || t.includes('DOUBLE') || t.includes('FLOAT') || t.includes('HUGEINT');
    const isTimeType = t.includes('TIMESTAMP') || t.includes('DATE') || t.includes('TIME');
    if (isNumeric || isTimeType) {
      if (!first) first = c.name;
      if (!guess && heur.some(h => c.name.toLowerCase().includes(h))) {
        guess = c.name;
      }
    }
  });
  return guess || first || null;
}
