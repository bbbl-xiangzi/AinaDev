import {test} from 'node:test';
import assert from 'node:assert/strict';
import {newPostHref, initialPostCategory} from '../lib/post-category.ts';
const cats=[{id:1,post_permission:'staff_only'}, {id:2,post_permission:'public'}, {id:3,post_permission:'closed'}, {id:4,allow_post:true}];
test('category entry carries its id; other pages do not inherit it',()=>{
 assert.equal(newPostHref('/c/4'),'/new?category_id=4');
 assert.equal(newPostHref('/c/2/'),'/new?category_id=2');
 for(const p of ['/', '/post/4', '/c/nope', '/assistant'])assert.equal(newPostHref(p),'/new');
});
test('preselect requested writable category and preserve permission boundaries',()=>{
 assert.equal(initialPostCategory(cats,'4','user'),4);
 assert.equal(initialPostCategory(cats,'1','super_admin'),1);
 for(const id of ['1','3','999','x','2e0',null])assert.equal(initialPostCategory(cats,id,'user'),2);
 assert.equal(initialPostCategory([],null,'user'),0);
 assert.equal(initialPostCategory([{id:3,post_permission:'closed'}],'3','super_admin'),0);
});

test('server capability allows assigned category admin, but still denies closed categories',()=>{
 assert.equal(initialPostCategory([{id:1,post_permission:'staff_only',can_post:true}], '1','user'),1);
 assert.equal(initialPostCategory([{id:1,post_permission:'closed',can_post:false}], '1','super_admin'),0);
});
