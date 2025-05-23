I really like Scuba (Meta's internal real-time database system). The distributed, real-time database part of Scuba is quite difficult (and expensive) to replicate, but I also really like Scuba's UI for doing queries, and I have found myself wishing that I have access to it even for "small" databases, e.g., I have a sqlite dataset I want to explore.

Pivotal ideas:

* Time series by default. In the dedicated "time series" view, there are many features specifically oriented towards working towards tables that represent events that occurred over time: the start, end, compare, aggregate and granularity fields all specially privilege the timestamp field. In fact, you can't log events to Scuba's backing data store without a timestamp, they always come with one. (Scuba also supports other views that don't presuppose a time series, but the time series is the most beloved and well used view.) This is in contrast to typical software which tries to generalize to arbitrary data first, with time series being added on later.

* It's all about exploration. Scuba is predicated on the idea that you don't know what you're looking for, that you are going to spend time tweaking queries and changing filters/grouping as part of an investigation to figure out why a system behaves the way it is. So the filters/comparisons/groupings you want to edit are always visible on the left sidebar, with the expectation that you're going to tweak the query to look at something else. Similarly, all the parameters of your query get saved into your URL, so your browser history can double up as a query history / you can easily share a query with someone else. This is contrast to typical software which is often oriented to making pretty dashboards and reports. (This function is important too, but it's not what I want in exploration mode!)

* You can fix data problems in the query editor. It's pretty common to have messed up and ended up with a database that doesn't have exactly the columns you need, or some columns that are corrupted in some way. Scuba has pretty robust support for defining custom columns with arbitrary SQL functions, grouping over them as if they were native functions, and doing so with minimal runtime cost (Scuba aims to turn around your query in milliseconds!) Having to go and run a huge data pipeline to fix your data is a big impediment to exploration; quick and easy custom columns means you can patch over problems when you're investigating and fix them for real later.

We're going to build a exploratory data analysis tool like Scuba for time series database (i.e., a database with a mandatory timestamp representing the time an event occurred).  We'll use DuckDB as the underlying SQL engine served from a Python server, and render the GUI/results as a webpage with vanilla HTML and JS. We'll use choices.js to support token inputs.  We define a token input to mean a text input element where as you type a dropdown displays with valid values, and if you select one or press enter, the selection turns into a token/chip that can only be deleted as one unit.

To start, we are going to support one views: samples.  The samples view only allows you to view individual samples from the database, subject to a filter. Our main UI concept is that there is a left sidebar that is the query editor, and the right side that shows the view.  The sidebar is always visible and defaults to the query parameters of the current view.  After you make changes to the query, clicking the "Dive" button updates the view.  The URL of the page encodes all of the values of the query (and gets updated when you Dive), so the browser's back button lets you view previous queries.

The query editor's job is to generate a SQL query, which then is applied on the database, and then the result visualized according to the view.

Here are the settings you can apply to the query. The help text should show up when you mouse over the field name:

* Start/End - Help text: "Sets the start/end of the time range to query. Can be any kind of datetime string. For example: 'April 23, 2014' or 'yesterday'." The UI for this selector supports both relative selections (now, -1 hour, -3 hours, -12 hours, -1 day, -3 days, -1 week, -1 fortnight, -30 days, -90 days, -1 month, -1 year) as well as specifying an absolute date.  The way this field is rendered is there is a free form text box, a drop down arrow (for the relative selectors), and then a calendar button (for date selection).
* Order By - Help text: "Choose a column to sort results by."  There is an ASC/DESC toggle next to it.
* Limit - Help text: "Choose the maximum number of results to show in the chart after any aggregations have been applied.  For example, a limit of 10 will show no more than 10 rows for a table, etc."
* Filters - You can create as many filters as you want. You can either write a filter using a UI or manual SQL. In the UI, filter consists of a column name, a relation (e.g., =, !=, <, >) and then a text field. The text field is a token input. It accepts multiple tokens for = relation, in which case we match using an OR for all options. 

There is also a "Columns" tab which lets you view all fields in the table, organized by their type. You can also define derived columns, by specifying a column name and SQL expression. Derived columns can be used for all parts of the UI, including filters/group by/etc. Columns have checkboxes indicating if we should SELECT them or not. Each selected column shows up in the graph.  There is an All/None link which can be used to select/deselect all checkboxes.

The query UI constructs a SQL query that intuitively has this form:

```
SELECT column, column, ...,
FROM table
WHERE time >= min-timestamp
AND time <= max-timestamp
[AND condition ...]
ORDER BY aggregate(column)
LIMIT number
```

You should write tests for the server backend, demonstrating that at specific query values we get back the correct rows of data.

## Running the server

Activate the virtual environment and run the Flask development server:

```bash
flask --app scubaduck.server run --debug
```

By default the server loads `sample.csv`. Set the `SCUBADUCK_DB` environment
variable to point at a different database file (CSV, SQLite or DuckDB) if you
want to use another dataset. The special value `TEST` starts the server with a
small in-memory SQLite dataset used by the automated tests. If the file does
not exist, the server will raise a `FileNotFoundError` during startup.
