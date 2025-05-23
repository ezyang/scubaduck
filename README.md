# ScubaDuck

ScubaDuck is a reimplementation of the frontend query interface for
[Scuba](https://research.facebook.com/publications/scuba-diving-into-data-at-facebook/)
(Meta's internal real-time database system) with DuckDB as the backing
database implementation.  This implementation misses most of the main value
add of Scuba (a distributed, real-time database that supports fast queries),
but I also think Scuba's UI for doing queries is great and I have found myself
wishing that I have access to it even for "small" databases, e.g., I have a
sqlite dataset I want to explore.  ScubaDuck is this interface.

<img width="1369" alt="Image" src="https://github.com/user-attachments/assets/e70cd5c8-e775-44b8-bab3-518a423b2267" />

This application was entirely vibe coded using OpenAI Codex.  It has no
third-party JS dependencies; everything was coded from scratch.

## Design Philosophy

* **Time series by default.** In the dedicated "time series" view, there are
  many features specifically oriented towards working towards tables that
  represent events that occurred over time: the start, end, compare, aggregate
  and granularity fields all specially privilege the timestamp field. In fact,
  you can't log events to Scuba's backing data store without a timestamp, they
  always come with one.  ScubaDuck is a little more flexible here (since you
  might be ingesting arbitrary database tables that weren't specifically
  designed for realtime databases), but it really shines when you have time
  series data.  This is in contrast to typical software which tries to work
  with arbitrary data first, with time series being added on later.

* **It's all about exploration.** Scuba is predicated on the idea that you
  don't know what you're looking for, that you are going to spend time
  tweaking queries and changing filters/grouping as part of an investigation
  to figure out why a system behaves the way it is. So the
  filters/comparisons/groupings you want to edit are always visible on the
  left sidebar, with the expectation that you're going to tweak the query to
  look at something else. Similarly, all the parameters of your query get
  saved into your URL, so your browser history can double up as a query
  history / you can easily share a query with someone else. This is contrast
  to typical software which is often oriented to making pretty dashboards and
  reports. (This function is important too, but it's not what I want in
  exploration mode!)

* **You can fix data problems in the query editor.** It's pretty common to
  have messed up and ended up with a database that doesn't have exactly the
  columns you need, or some columns that are corrupted in some way. Scuba has
  pretty robust support for defining custom columns with arbitrary SQL
  functions, grouping over them as if they were native functions, and doing so
  with minimal runtime cost (Scuba aims to turn around your query in
  milliseconds!) Having to go and run a huge data pipeline to fix your data is
  a big impediment to exploration; quick and easy custom columns means you can
  patch over problems when you're investigating and fix them for real later.

## Development

```
uv sync --frozen
SCUBADUCK_DB=/path/to/foo.sqlite flask --app scubaduck.server run --debug
```

DuckDB databases and Parquet files work too.  Omit to get a simple test dataset, or
`SCUBADUCK_DB=TEST` for a more complicated test dataset.

## How to use it

If you don't have a dataset handy,
[NYC TLC Yellow Taxi Trip Records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
has convenient PARQUET files that are time series.  You could for example
run ScubaDuck on
[January 2025 Yellow Taxi Trip Records](https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-01.parquet)
(which is where the screenshot above was taken from).

After you've loaded a database and navigate to the application, the home page
will pop up the first table in your database and display a hundred samples
from it.  When you're working with a table for the first time, it's a good
idea to look at some samples by hand and get a feel for what's stored in it.
(Better is to have designed the table with ScubaDuck visualization in mind.)

Samples lets you look at entries one-by-one, but typically you'll have too
many things to look at one by one.  Table gives you simple aggregation
capabilities: you can use Group by to get some high level aggregate statistics
at various breakdowns.

The real juice of Scuba is time series visualization.  Assuming your table has
a time column, you can plot any numeric column on a graph.  With group by, you
can split into multiple series, aggregating over each value of the group by.
You can easily drill down / drill back up, looking for patterns that only show
up on certain splits.

Whenever you Dive, ScubaDuck will update your URL with all of the information
for your query.  If you save these URLs, you have a durable record of the
query you made (assuming your ScubaDuck server is still running!)

Happy diving!

## Roadmap

- Scuba works best with denormalized tables that don't require JOINs.  Scuba
  at Meta in fact does not support JOINs.  DuckDB does support JOINs, so we
  need to come up with a good UI for exposing them.

- There is some extra metadata you might want to persistently save about a
  database that will help ScubaDuck show it to you in the future.  For
  example, ScubaDuck will always abbreviate integers with SI prefixes, but if
  an integer is actually an ID of some sort, this is counterproductive and you
  probably prefer to render the actual ID.  Similarly, ScubaDuck tries to
  infer what the timestamp column is, but if it gets it wrong you'd like to
  durably save the correct choice.  Unfortunately, ScubaDuck as it currently
  exists is entirely stateless (state lives only in the URL parameters you get
  when you Dive.)  I'm thinking of adding a sidecar file that ScubaDuck can
  write to next to your database that contains some metadata and then expand
  the UI to allow for more complicated persistent settings.

- Codex is not very smart and mostly implemented things exactly as I asked for
  it.  This means there are many places where there are bugs or lacking polish
  because I hadn't realized I needed to prompt for it.  Bug reports are
  appreciated, I will feed them to Codex to get them fixed.
