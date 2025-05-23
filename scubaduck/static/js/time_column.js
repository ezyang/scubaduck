// Helper for choosing a default time column based on column names/types
function guessTimeColumn(columns) {
  const heur = ['timestamp','created','created_at','event_time','time','date','occurred','happened','logged'];
  let heurGuess = null;
  let timestamp = null;
  columns.forEach(c => {
    const t = (c.type || '').toUpperCase();
    const isNumeric = t.includes('INT') || t.includes('DECIMAL') || t.includes('NUMERIC') ||
                      t.includes('REAL') || t.includes('DOUBLE') || t.includes('FLOAT') || t.includes('HUGEINT');
    const isTimeType = t.includes('TIMESTAMP') || t.includes('DATE') || t.includes('TIME');
    if (heur.some(h => c.name.toLowerCase().includes(h)) && (isTimeType || isNumeric)) {
      if (!heurGuess) heurGuess = c.name;
    }
    if (!timestamp && isTimeType) {
      timestamp = c.name;
    }
  });
  return heurGuess || timestamp || null;
}
