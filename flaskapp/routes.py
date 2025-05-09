from flask import render_template, flash, redirect, url_for, request
from flaskapp import app, db
from flaskapp.models import BlogPost, IpView, Day, UkData # accessing the Database
from flaskapp.forms import PostForm
import datetime
from sqlalchemy import inspect
import plotly.express as px
import pandas as pd
import json
import plotly
import seaborn as sns
from plotly.subplots import make_subplots
import plotly.graph_objects as go


# Route for the home page, which is where the blog posts will be shown
@app.route("/")
@app.route("/home")
def home():
    # Querying all blog posts from the database
    posts = BlogPost.query.all()
    return render_template('home.html', posts=posts)


# Route for the about page
@app.route("/about")
def about():
    return render_template('about.html', title='About page')


# Route to where users add posts (needs to accept get and post requests)
@app.route("/post/new", methods=['GET', 'POST'])
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = BlogPost(title=form.title.data, content=form.content.data, user_id=1)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post', form=form)


# Route to the dashboard page
@app.route('/dashboard')
def dashboard():
    days = Day.query.all()
    df = pd.DataFrame([{'Date': day.id, 'Page views': day.views} for day in days])

    fig = px.bar(df, x='Date', y='Page views')

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template('dashboard.html', title='Page views per day', graphJSON=graphJSON)


@app.before_request
def before_request_func():
    day_id = datetime.date.today()  # get our day_id
    client_ip = request.remote_addr  # get the ip address of where the client request came from

    query = Day.query.filter_by(id=day_id)  # try to get the row associated to the current day
    if query.count() > 0:
        # the current day is already in table, simply increment its views
        current_day = query.first()
        current_day.views += 1
    else:
        # the current day does not exist, it's the first view for the day.
        current_day = Day(id=day_id, views=1)
        db.session.add(current_day)  # insert a new day into the day table

    query = IpView.query.filter_by(ip=client_ip, date_id=day_id)
    if query.count() == 0:  # check if it's the first time a viewer from this ip address is viewing the website
        ip_view = IpView(ip=client_ip, date_id=day_id)
        db.session.add(ip_view)  # insert into the ip_view table

    db.session.commit()  # commit all the changes to the database

# get the data to see what is in there
# CSS styling is by GPT
@app.route('/data')
def data():
    data = UkData.query.limit(10).all()  
    mapper = inspect(UkData)
    _ = [column.key for column in mapper.columns]
    return render_template('my_table.html', data=data)

# route to my first plot: Green Party support by constituency
@app.route('/green_vote')
def green_vote():
    # get the data 
    data = UkData.query.filter_by(country = "England").with_entities( #just data for england 
        UkData.constituency_name,
        UkData.GreenVote19,
        UkData.TotalVote19).all()


    df = pd.DataFrame(data, columns=["Constituency", "GreenVote", "TotalVote"])


    df["Green Vote Share"] = (df["GreenVote"]/df["TotalVote"]) * 100

    # sort graph and create sub-dfs which only include biggest & smallest observations
    df_low  = df.nsmallest(10, columns="Green Vote Share")
    df_high = df.nlargest(10, columns="Green Vote Share").sort_values(by="Green Vote Share", ascending=True)

    # necessary to ensure the graphs are on the same colour scale later 
    df = df.sort_values(by="Green Vote Share", ascending=True)
    vmin = df["Green Vote Share"].min()
    vmax = df["Green Vote Share"].max()


    # make plot 
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("10 Worst Green-share Constituencies",
                        "10 Best Green-share Constituencies")
    )


    # col 1
    fig.add_trace(
        go.Bar(
            x=df_low["Constituency"],
            y=df_low["Green Vote Share"],
            showlegend=False, # has to be disabled
            marker=dict(color=df_low["Green Vote Share"],
                        colorscale=px.colors.sequential.Magma,
                        cmin=vmin,               # ensures that both plots have the same colour scale 
                        cmax=vmax                
        ),

            # Custom hover-box: Constituency name and Vote share as NN,NN%
            hovertemplate=(
                "%{x}<br>"
                "Green share: %{y:.2f}%<extra></extra>" # extra extra dops the weird "trace name" box
            )
        ),
        row=1, col=1
    )

    # col 2
    fig.add_trace(
        go.Bar(
            x=df_high["Constituency"],
            y=df_high["Green Vote Share"],
            showlegend=False,
            marker=dict(color=df_high["Green Vote Share"],
                        colorscale=px.colors.sequential.Magma,
                        cmin=vmin,               # same minimum as in fig 1 
                        cmax=vmax                # same maximum as in fig 1
        ),
            hovertemplate=(
                "%{x}<br>"
                "Green share: %{y:.2f}%<extra></extra>"
            )
        ),
        row=1, col=2
    )

    # tidy up axes & layout
    fig.update_layout(
        title_text="Green Vote Share in the 10 Weakest and Strongest Constituencies (2019)",
        height=600, width=1000,
        margin=dict(t=100),
    )
    
    
    fig.update_xaxes(tickangle=-45, title_text="Constituency", row=1, col=1)
    fig.update_xaxes(tickangle=-45, title_text="Constituency", row=1, col=2)
    fig.update_yaxes(title_text="Green Vote Share (%)", row=1, col=1)
    fig.update_yaxes(title_text="Green Vote Share (%)", row=1, col=2)

    # it HAS to be HTML - JSON ruins the graph 
    fig_html= fig.to_html(full_html=False)

    # Pass the JSON to the HTML template
    return render_template('green_vote.html', title='Green Party Vote Share 2019', fig_html=fig_html)


# route to my second plot
@app.route('/retired_impact')
def retired_impact(): # everything below needs to be changed 
    # get the data 
    data = UkData.query.filter_by(country = "England").with_entities( #just data for england 
        UkData.constituency_name,
        UkData.GreenVote19,
        UkData.TotalVote19,
        UkData.c11Retired).all()
    
    df = pd.DataFrame(data, columns=["Constituency", "GreenVote", "TotalVote", "Retirees"])

    df["GreenVoteShare"] = df["GreenVote"]/df["TotalVote"] * 100

    fig_2 = px.scatter(df, x="Retirees", y="GreenVoteShare",
                      title = "Correlation of Green Support with Retiree Share in Population",
                      color="Retirees", color_continuous_scale=px.colors.sequential.Magma,
                      labels = {"Retirees": "Population Share of Retirees in %",
                                "GreenVoteShare": "Vote Share of Greens"},
                                hover_data={"Constituency": True}) #so Constituency appears in the hover box 
    
    fig_2.update_traces(
    hovertemplate=(
        "Constituency: %{customdata[0]}<br>"
        "Retiree Share: %{x:.2f}%<br>"
        "Green Vote Share: %{y:.2f}%<extra></extra>"
    )
)

    fig_2.update_layout(coloraxis_colorbar=dict(title="Retiree Share (%)")) 

    fig_2_html= fig_2.to_html(full_html=False)
    return render_template("retired_impact.html", fig_2_html=fig_2_html)
