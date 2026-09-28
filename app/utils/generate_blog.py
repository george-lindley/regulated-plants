import os
import markdown
import frontmatter
import bleach
from datetime import date, datetime
from app.config import Config


def _date_to_iso(d):
    """Normalize frontmatter dates (date, datetime, or str) to YYYY-MM-DD for sort and display."""
    if d is None:
        return datetime.now().strftime("%Y-%m-%d")
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if isinstance(d, str):
        return d.strip()[:10]
    return str(d)[:10]


ALLOWED_BLOG_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {"p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "img"}
)
ALLOWED_BLOG_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "loading"],
}
ALLOWED_BLOG_PROTOCOLS = set(bleach.sanitizer.ALLOWED_PROTOCOLS).union({"mailto"})

class BlogGenerator:
    def __init__(self):
        self.blog_posts = self.generate_blog_posts()
        self.tags = self.generate_tags()

    @staticmethod
    def read_markdown_file(file_path):
        """Read and parse markdown file with frontmatter"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return frontmatter.loads(content)

    def generate_tags(self):
        """Generate a dictionary of all tags and their counts"""
        tags = {}
        for post in self.blog_posts:
            for tag in post.get('tags', []):
                tags[tag] = tags.get(tag, 0) + 1
        return tags

    def get_posts_by_tag(self, tag):
        """Filter posts by tag"""
        return [post for post in self.blog_posts if tag in post.get('tags', [])]
    
    def get_post_image_path(self, image_filename):
        """Generate the correct path for blog post images"""
        path = f'/static/blog_images/{image_filename}'
        return path

    def sanitize_post_html(self, html_content):
        """Sanitize rendered markdown to prevent script/content injection."""
        return bleach.clean(
            html_content,
            tags=ALLOWED_BLOG_TAGS,
            attributes=ALLOWED_BLOG_ATTRIBUTES,
            protocols=ALLOWED_BLOG_PROTOCOLS,
            strip=True,
        )

    def generate_blog_posts(self):
        """Generate list of blog posts from markdown files"""
        markdown_files = sorted([f for f in os.listdir(Config.BLOG_DIR) if f.endswith('.md')])
        blog_posts = []

        for filename in markdown_files:
            file_path = os.path.join(Config.BLOG_DIR, filename)
            post = self.read_markdown_file(file_path)
            
            metadata = post.metadata
            content = post.content

            # Create slug from filename first (for file paths)
            file_slug = os.path.splitext(filename)[0]
            
            # Handle feature image using file_slug for directory
            image = metadata.get('image')
            if image:
                if not image.startswith('/'):
                    image = self.get_post_image_path(image)

            # Create URL-friendly slug from title for URLs
            url_slug = metadata.get('title', 'Untitled').lower()
            url_slug = ''.join(c if c.isalnum() or c.isspace() else '' for c in url_slug)
            url_slug = '-'.join(url_slug.split())

            # Generate excerpt if not provided
            excerpt = metadata.get('excerpt')
            if not excerpt:
                # Filter out image markdown lines and headers
                content_lines = [
                    line.strip() 
                    for line in content.splitlines() 
                    if not (line.strip().startswith('#') or 
                        line.strip().startswith('![') or
                        line.strip().startswith('![]'))
                ]
                
                # Join the filtered lines
                filtered_content = " ".join(content_lines)
                
                # Remove markdown formatting
                # Extract only the text from markdown links [text](url)
                while '[' in filtered_content and '](' in filtered_content:
                    start = filtered_content.find('[')
                    middle = filtered_content.find('](')
                    end = filtered_content.find(')', middle)
                    if start != -1 and middle != -1 and end != -1:
                        link_text = filtered_content[start + 1:middle]
                        filtered_content = filtered_content[:start] + link_text + filtered_content[end + 1:]
                    else:
                        break
                
                # Remove asterisks
                filtered_content = filtered_content.replace('*', '')
                
                # Get first 50 words
                excerpt = " ".join(filtered_content.split()[:50]) + "..."

            # Convert Markdown to HTML
            html_content = markdown.markdown(
                content,
                extensions=['extra', 'toc', 'meta']
            )
            html_content = self.sanitize_post_html(html_content)

            blog_posts.append({
                "title": metadata.get('title', 'Untitled'),
                "date": _date_to_iso(metadata.get("date")),
                "author": metadata.get('author', Config.SITE_AUTHOR),
                "tags": metadata.get('tags', []),
                "excerpt": excerpt,
                "content": html_content,
                "slug": url_slug,
                "image": image
            })

        return sorted(blog_posts, key=lambda x: x['date'], reverse=True)
        
    def get_post_by_slug(self, slug):
        """Get blog post by slug"""
        for post in self.blog_posts:
            if post["slug"] == slug:
                return post
        return None
