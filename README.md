# Reference to QR Code Converter

A Flask application that converts academic reference files (BibTeX, RDF, RIS, EndNote XML) into QR codes linking to formatted reference lists. It also supports creating QR codes for Google Documents.

## Features

- Convert reference files (.bib, .rdf, .ris, .xml) to QR codes
- Link directly to Google Docs with QR codes
- Persistent storage of reference data
- Automatic expiration of old references
- Admin tools for database monitoring and maintenance

## Quick Start

The application comes with scripts to easily run and stop the server:

1. Start the application:
   ```bash
   ./run_app.sh
   ```

2. Access the application at http://localhost:5000 in your browser

3. Stop the application (if needed):
   ```bash
   ./stop_app.sh
   ```

## Google Docs Integration

The application now supports creating QR codes that link directly to Google Documents:

1. Choose "Option 2: Link to Google Document" on the main page
2. Enter an optional title for the document
3. Paste the Google Docs URL
4. Generate a QR code that will redirect users directly to your document

This is useful for:
- Sharing reference lists maintained in Google Docs
- Linking to collaborative documents
- Providing access to formatted references that don't fit the standard formats

## New Database Feature

The application uses SQLAlchemy to store references in a persistent database instead of in-memory storage. This means:

- Reference lists persist across server restarts
- References can have expiration dates (default: 30 days)
- Automatic cleanup of expired references

### Database Setup

By default, the application uses SQLite for development, which requires no additional setup:

```
# SQLite database will be created automatically at:
references.db
```

For production, you can configure PostgreSQL by setting the `DATABASE_URL` environment variable:

```bash
# Example PostgreSQL connection
export DATABASE_URL=postgresql://username:password@localhost/references
```

Then modify `database.py` to use this environment variable.

### Database Maintenance and Monitoring

The application includes administrative endpoints to help manage the database:

#### Cleanup Endpoint

Expired references can be cleaned up automatically using the cleanup endpoint:

```
http://localhost:5000/maintenance/cleanup?key=change_this_key_for_production
```

Set up a cron job or scheduled task to call this endpoint regularly (e.g., daily):

```bash
# Example cron job (daily at 2 AM)
0 2 * * * curl https://your-domain.com/maintenance/cleanup?key=your_maintenance_key
```

#### Delete All References

If you need to completely reset the database and remove all reference lists:

```
http://localhost:5000/admin/delete-all?key=change_this_key_for_production
```

**Warning**: This will permanently delete all references from the database. A confirmation page will be shown before deletion.

#### Database Statistics

You can view statistics about the database contents at this direct URL:

```
http://localhost:5000/admin/stats?key=change_this_key_for_production
```

This shows:
- Total number of reference lists
- Number of active vs. expired reference lists
- Details about the most recently created reference lists
- Links to view the references
- Option to clean up expired references

The maintenance key is set in `app.py` and should be changed to a secure value in production.

## Installation and Setup

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Access the application at http://localhost:5000 