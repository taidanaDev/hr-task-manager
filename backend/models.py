from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from enum import Enum
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()

class RoleEnum(str, Enum):
    MANAGER = "manager"
    EMPLOYEE = "employee"
    ADMIN = "admin"

class PriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class StatusEnum(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

def get_current_time():
    return datetime.utcnow()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.EMPLOYEE)
    password_hash = db.Column(db.String(128), nullable=False)
    position = db.Column(db.String(100), nullable=True)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Column for Greedy Algorithm (Workload)
    workload = db.Column(db.Integer, default=0, nullable=False)
    
    created_at = db.Column(db.DateTime, default=get_current_time, nullable=False)
    
    change_password = db.Column(db.Boolean, default=True, nullable=False)
    
    reports = db.relationship('User', backref=db.backref('supervisor', remote_side=[id]), lazy='dynamic')

    def __repr__(self):
        return f"<User id={self.id} name={self.name} role={self.role}>"

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority = db.Column(db.Enum(PriorityEnum), nullable=False, default=PriorityEnum.MEDIUM)
    status = db.Column(db.Enum(StatusEnum), nullable=False, default=StatusEnum.PENDING)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_current_time, nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)

    def priority_value(self):
        priority_mapping = {
            PriorityEnum.LOW: 2,
            PriorityEnum.MEDIUM: 1,
            PriorityEnum.HIGH: 0
        }
        return priority_mapping[self.priority]
    
User.assigned_tasks = db.relationship(
    'Task',
    backref='assignee',
    lazy='dynamic',
    foreign_keys=[Task.assignee_id]
)

User.created_tasks = db.relationship(
    'Task',
    backref='creator',
    lazy='dynamic',
    foreign_keys=[Task.creator_id]
)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=get_current_time, nullable=False)

    user = db.relationship('User', backref=db.backref('notifications', lazy='joined'))

    def __repr__(self):
        return f"<Notification id={self.id} user_id={self.user_id} read={self.read}>"

#Task Dependency Model (For Graph/Topological Sort)

class TaskDependency(db.Model):
    """
    Represents a dependency relationship: prereq_id must be done before dependent_id.
    This model serves as the edge list for the Task Graph.
    """
    __tablename__ = 'task_dependencies'
    id = db.Column(db.Integer, primary_key=True)
    

    prereq_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    
    dependent_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)

    __table_args__ = (
        UniqueConstraint('prereq_id', 'dependent_id', name='_unique_dependency_uc'),
    )

    prerequisite = db.relationship(
        'Task', 
        foreign_keys=[prereq_id], 
        backref=db.backref('dependencies_as_prereq', lazy='dynamic')
    )
    dependent = db.relationship(
        'Task', 
        foreign_keys=[dependent_id], 
        backref=db.backref('dependencies_as_dependent', lazy='dynamic')
    )

    def __repr__(self):
        return f'<TaskDependency {self.prereq_id} -> {self.dependent_id}>'